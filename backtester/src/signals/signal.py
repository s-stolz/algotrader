import pandas as pd


def _align_for_comparison(
    left: pd.DataFrame,
    right: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if left.shape[1] != right.shape[1]:
        raise ValueError("Input DataFrames must have the same number of columns.")
    if not left.columns.equals(right.columns):
        right = right.copy()
        right.columns = left.columns
    return left, right


def _normalize_output_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels > 1:
        df = df.copy()
        df.columns = df.columns.droplevel(0)
    return df


def crossover(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    df1, df2 = _align_for_comparison(df1, df2)
    valid_mask = (df1.notna() & df2.notna()).shift(1, fill_value=False)

    df = df1 > df2

    df_shifted = df.shift(1, fill_value=False)

    upward_cross = df & (~df_shifted) & valid_mask

    return _normalize_output_columns(upward_cross)


def crossunder(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    df1, df2 = _align_for_comparison(df1, df2)
    valid_mask = (df1.notna() & df2.notna()).shift(1, fill_value=False)

    df = df1 < df2

    df_shifted = df.shift(1, fill_value=False)

    downward_cross = df & (~df_shifted) & valid_mask

    return _normalize_output_columns(downward_cross)


def above(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    df1, df2 = _align_for_comparison(df1, df2)
    df = df1 > df2

    return _normalize_output_columns(df)


def below(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    df1, df2 = _align_for_comparison(df1, df2)
    df = df1 < df2

    return _normalize_output_columns(df)
