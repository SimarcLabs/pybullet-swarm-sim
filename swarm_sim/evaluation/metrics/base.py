"""Base Metric for the metric registry."""

from abc import ABC, abstractmethod
from typing import List

from swarm_sim.telemetry.frame import FrameSnapshot


class BaseMetric(ABC):
    """Abstract base class for all swarm evaluation metrics."""

    @classmethod
    def get_name(cls) -> str:
        return cls.__name__

    @abstractmethod
    def compute(self, frames: List[FrameSnapshot]) -> float:
        """Compute the final metric value over the entire time series.
        
        Parameters
        ----------
        frames : List[FrameSnapshot]
            The full history of the simulation run.

        Returns
        -------
        float
            The evaluated score. By convention, higher is better, and 
            the score is normalized between 0.0 and 1.0 where possible.
        """
        pass
