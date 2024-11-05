import pandas as pd

def crossover(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    valid_mask = df1.notna() & df2.notna()
    valid_mask = valid_mask.shift(1).fillna(False)

    df = (df1 > df2)

    df_shifted = df.shift(1).fillna(False)

    upward_cross = df & (~df_shifted) & valid_mask
    
    return upward_cross

def crossunder(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    valid_mask = df1.notna() & df2.notna()
    valid_mask = valid_mask.shift(1).fillna(False)

    df = df1 < df2
    
    df_shifted = df.shift(1).fillna(False)

    downward_cross = df & (~df_shifted) & valid_mask
    
    return downward_cross

def above(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    df = df1 > df2

    return df

def below(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    df = df1 < df2
    
    return df