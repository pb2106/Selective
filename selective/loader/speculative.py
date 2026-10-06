"""
Background Speculative Loading Scheduler for Selective.
Prepares likely-needed modules in the background (parsing, AST transforming, compiling, caching)
without executing module initialization code prematurely.
"""

import sys
import time
import queue
import threading
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from types import CodeType
from selective.loader.cache_manager import BytecodeCacheManager
from selective.loader.miss_path import is_package_tainted, get_module_lock

logger = logging.getLogger("selective.speculative")

class SpeculativeTask:
    def __init__(self, module_name: str, parent_package: str = "", confidence: float = 1.0, priority: int = 10):
        self.module_name = module_name
        self.parent_package = parent_package or module_name.split(".")[0]
        self.confidence = confidence
        self.priority = priority

    def __lt__(self, other: "SpeculativeTask") -> bool:
        # Higher confidence and lower priority number comes first
        if self.confidence != other.confidence:
            return self.confidence > other.confidence
        return self.priority < other.priority

class SpeculativeScheduler:
    _instance: Optional["SpeculativeScheduler"] = None
    _instance_lock = threading.Lock()

    def __init__(self, workers: int = 2, max_tasks: int = 32):
        self.workers = workers
        self.max_tasks = max_tasks
        self._task_queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=max_tasks)
        self._queued_modules: Set[str] = set()
        self._prepared_code_cache: Dict[str, CodeType] = {}
        self._prepared_times: Dict[str, float] = {}
        self._threads: List[threading.Thread] = []
        self._running = False
        self._lock = threading.Lock()
        self.cache_manager = BytecodeCacheManager()
        self.total_avoided_ms: float = 0.0

    @classmethod
    def get_instance(cls) -> "SpeculativeScheduler":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            for i in range(self.workers):
                t = threading.Thread(target=self._worker_loop, daemon=True, name=f"selective-speculative-{i}")
                t.start()
                self._threads.append(t)

    def shutdown(self, timeout: float = 1.0):
        with self._lock:
            if not self._running:
                return
            self._running = False

        # Unblock worker threads
        for _ in range(self.workers):
            try:
                self._task_queue.put_nowait((0, SpeculativeTask("__SHUTDOWN__", priority=-1)))
            except queue.Full:
                pass

        for t in self._threads:
            t.join(timeout=timeout)
        self._threads.clear()

    def schedule(self, module_name: str, parent_package: str = "", confidence: float = 1.0, priority: int = 10):
        if not self._running:
            self.start()

        with self._lock:
            if module_name in self._queued_modules or module_name in sys.modules:
                return
            if is_package_tainted(parent_package or module_name.split(".")[0]):
                return
            self._queued_modules.add(module_name)

        task = SpeculativeTask(module_name, parent_package, confidence, priority)
        try:
            # Rank item: (-confidence, priority, task)
            self._task_queue.put_nowait((-confidence, priority, task))
        except queue.Full:
            logger.debug(f"Speculative task queue full, dropping task for {module_name}")

    def _worker_loop(self):
        while self._running:
            try:
                item = self._task_queue.get(timeout=0.2)
                _, _, task = item

                if task.module_name == "__SHUTDOWN__":
                    self._task_queue.task_done()
                    break

                self._process_task(task)
                self._task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.debug(f"Speculative task error: {e}")

    def _process_task(self, task: SpeculativeTask):
        mod_name = task.module_name
        pkg_name = task.parent_package

        if is_package_tainted(pkg_name) or mod_name in sys.modules:
            return

        t0 = time.perf_counter()
        try:
            import importlib.util
            spec = importlib.util.find_spec(mod_name)
            if spec is not None and spec.origin and spec.origin.endswith(".py"):
                path = Path(spec.origin)
                source_text = path.read_text(encoding="utf-8", errors="replace")
                
                # Check/populate transformed bytecode cache (WITHOUT executing module body code!)
                cached_code = self.cache_manager.get(source_text, "speculative")
                if cached_code is None:
                    import ast
                    from selective.loader.transformer import SelectiveTransformer
                    tree = ast.parse(source_text, filename=str(path))
                    transformer = SelectiveTransformer(mod_name)
                    transformed_tree = transformer.transform(tree)
                    compiled_code = compile(transformed_tree, filename=str(path), mode="exec")
                    self.cache_manager.put(source_text, "speculative", compiled_code)
                    code_to_store = compiled_code
                else:
                    code_to_store = cached_code

                prep_time_ms = (time.perf_counter() - t0) * 1000.0

                with self._lock:
                    self._prepared_code_cache[mod_name] = code_to_store
                    self._prepared_times[mod_name] = prep_time_ms
                    self.total_avoided_ms += prep_time_ms

                logger.debug(f"Prepared speculative module '{mod_name}' in {prep_time_ms:.2f}ms (confidence={task.confidence:.2f})")
        except Exception as err:
            logger.debug(f"Failed speculative preparation for '{mod_name}': {err}")

    def get_prepared_code(self, module_name: str) -> Optional[CodeType]:
        with self._lock:
            return self._prepared_code_cache.get(module_name)

    def get_diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "speculative_enabled": self._running,
                "workers": self.workers,
                "prepared_count": len(self._prepared_code_cache),
                "prepared_modules": list(self._prepared_code_cache.keys()),
                "total_avoided_prep_ms": round(self.total_avoided_ms, 2)
            }

def prefetch(module_name: str, confidence: float = 1.0, parent_package: str = ""):
    """Public runtime API for explicit speculative prefetching."""
    scheduler = SpeculativeScheduler.get_instance()
    scheduler.schedule(module_name, parent_package=parent_package, confidence=confidence, priority=1)
