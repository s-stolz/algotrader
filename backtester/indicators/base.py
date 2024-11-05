from typing import Protocol
import pandas as pd

class Indicator(Protocol):
    def run(self) -> pd.DataFrame: ...