"""Trading job scheduler for periodic execution."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class TradingScheduler:
    """
    Schedules trading jobs at fixed intervals.
    Default: Every 15 minutes aligned to clock (00, 15, 30, 45).
    """

    def __init__(self, interval_minutes: int = 15):
        """Initialize scheduler.

        Args:
            interval_minutes: Minutes between trading cycles.
        """
        self.interval = interval_minutes
        self.scheduler = AsyncIOScheduler()
        self._is_running = False

    def start(self, trading_job: Callable, run_immediately: bool = True):
        """
        Starts the scheduler with the trading job.

        Args:
            trading_job: Async function to execute on each interval.
            run_immediately: Whether to run the job immediately on start.
        """
        if self._is_running:
            logger.warning("Scheduler already running")
            return

        # Calculate aligned start time
        next_aligned = self._get_next_aligned_time()

        # Use cron trigger for precise alignment to clock
        # This ensures we run at :00, :15, :30, :45 (for 15min interval)
        if self.interval == 15:
            trigger = CronTrigger(minute="0,15,30,45")
        elif self.interval == 30:
            trigger = CronTrigger(minute="0,30")
        elif self.interval == 60:
            trigger = CronTrigger(minute="0")
        else:
            # For non-standard intervals, use interval trigger
            trigger = IntervalTrigger(
                minutes=self.interval,
                start_date=next_aligned,
            )

        self.scheduler.add_job(
            trading_job,
            trigger=trigger,
            id="trading_cycle",
            name="Bitcoin Prediction Trading",
            max_instances=1,  # Prevent overlapping executions
            coalesce=True,  # Combine missed runs
            misfire_grace_time=60,  # Allow 60s grace period
        )

        # Add daily reset job at midnight UTC
        self.scheduler.add_job(
            self._daily_reset_placeholder,
            trigger=CronTrigger(hour=0, minute=0),
            id="daily_reset",
            name="Daily Counter Reset",
        )

        self.scheduler.start()
        self._is_running = True

        logger.info(
            f"Scheduler started:\n"
            f"  Interval: {self.interval} minutes\n"
            f"  Next run: {next_aligned.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        # Run immediately if requested
        if run_immediately:
            logger.info("Running initial trading cycle...")
            asyncio.create_task(trading_job())

    async def _daily_reset_placeholder(self):
        """Placeholder for daily reset. Override in main app."""
        logger.info("Daily reset triggered (placeholder)")

    def set_daily_reset_callback(self, callback: Callable):
        """Set the callback for daily reset."""
        self.scheduler.reschedule_job(
            "daily_reset",
            trigger=CronTrigger(hour=0, minute=0),
        )
        self.scheduler.modify_job("daily_reset", func=callback)

    def _get_next_aligned_time(self) -> datetime:
        """Gets next time aligned to interval (e.g., :00, :15, :30, :45)."""
        now = datetime.now(timezone.utc)

        # Calculate next aligned minute
        current_minute = now.minute
        aligned_minute = ((current_minute // self.interval) + 1) * self.interval

        if aligned_minute >= 60:
            # Roll over to next hour
            next_time = now.replace(
                hour=(now.hour + 1) % 24,
                minute=aligned_minute - 60,
                second=0,
                microsecond=0,
            )
            # Handle day rollover
            if now.hour == 23:
                from datetime import timedelta
                next_time = next_time + timedelta(days=1)
        else:
            next_time = now.replace(
                minute=aligned_minute,
                second=0,
                microsecond=0,
            )

        return next_time

    def stop(self):
        """Gracefully stops the scheduler."""
        if not self._is_running:
            return

        self.scheduler.shutdown(wait=True)
        self._is_running = False
        logger.info("Scheduler stopped")

    def pause(self):
        """Pause the scheduler."""
        if self._is_running:
            self.scheduler.pause()
            logger.info("Scheduler paused")

    def resume(self):
        """Resume the scheduler."""
        if self._is_running:
            self.scheduler.resume()
            logger.info("Scheduler resumed")

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._is_running

    def get_next_run_time(self) -> Optional[datetime]:
        """Get the next scheduled run time."""
        job = self.scheduler.get_job("trading_cycle")
        if job:
            return job.next_run_time
        return None

    def get_status(self) -> dict:
        """Get scheduler status."""
        next_run = self.get_next_run_time()
        return {
            "running": self._is_running,
            "interval_minutes": self.interval,
            "next_run": next_run.isoformat() if next_run else None,
            "jobs": len(self.scheduler.get_jobs()),
        }
