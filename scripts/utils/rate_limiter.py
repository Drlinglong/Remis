# scripts/utils/rate_limiter.py
import time
import threading
import logging

class RateLimiter:
    """
    一个简单的全局 RPM (每分钟请求数) 速率限制器。
    使用线程锁确保多线程环境下的调用频率。
    """
    def __init__(self, rpm=40):
        self._rpm = rpm
        self._interval = 60.0 / rpm if rpm > 0 else 0
        self._last_call = 0.0
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    @property
    def rpm(self):
        return self._rpm

    def update_rpm(self, rpm):
        """动态更新 RPM 限制。"""
        with self._lock:
            self._rpm = rpm
            self._interval = 60.0 / rpm if rpm > 0 else 0
            self.logger.info(f"Rate limiter updated: {rpm} RPM (Interval: {self._interval:.2f}s)")

    def wait(self):
        """
        在继续之前等待，直到满足 RPM 限制。
        计算等待时间并在锁外执行 sleep，以允许其他线程预约未来的时间槽。
        """
        if self._rpm <= 0:
            return
        
        sleep_time = 0
        with self._lock:
            now = time.time()
            
            # 如果上次调用时间比现在还早（说明很久没用了），则从现在开始算
            # 否则从预定的下一次可用时间开始算
            base_time = max(now, self._last_call)
            target_time = base_time + self._interval
            
            sleep_time = target_time - now
            self._last_call = target_time

        if sleep_time > 0:
            # self.logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)

# 全局单例
rate_limiter = RateLimiter()
