import pandas as pd
import numpy as np
from scipy.stats import norm
import warnings

def simple_copy(
    df: pd.DataFrame,
    timestamp_col: str,
    value_col: str,
    start: pd.Timestamp, #must be localized in UTC
    end: pd.Timestamp, #must be localized in UTC
    respect_time = True,
    respect_weekdays = True,
) -> pd.DataFrame:
    """
    Naive forecast: copy the values between start and end (both included)
    and append them at the end of the dataframe.
    """
    # check localization
    if start.tzinfo != "UTC":        # todo check that a missing tzinfo does raise the error # todo check that a pd.na falls here
        raise ValueError(f"Missing or wrong tzinfo for start (expected to be in UTC): {start}")
    if end.tzinfo != "UTC":
        raise ValueError(f"Missing or wrong tzinfo for end (expected to be in UTC): {end}")

    out = df.copy()

    if end <= start:
        raise ValueError("end must be strictly after start.")
    if not df[timestamp_col].eq(start).any(): # correct test for tz-aware data
    # this other test fails, because ".values" is not tz-aware : if start not in y_15min[timestamp_col].values
        raise ValueError(f"start {start} must be present in {timestamp_col}, spanning {df[timestamp_col].min(), df[timestamp_col].max()}")
    if not df[timestamp_col].eq(end).any():
        raise ValueError(f"end {end} must be present in {timestamp_col}, spanning {df[timestamp_col].min(), df[timestamp_col].max()}")
    elapsed = df[timestamp_col].diff()
    if elapsed.value_counts().size != 1:
        raise ValueError(f"The elapsed time in {timestamp_col} is inconsistent, should be nomalized.")

    #
    mask = (out[timestamp_col] >= start) & (out[timestamp_col] <= end)
    to_copy = out.loc[mask, [timestamp_col, value_col]].copy()
    if to_copy.empty:
        return out

    # extend the end of the df
    ### might be possible to factorize with the same content in copy_median_values
    elapsed = to_copy[timestamp_col].diff()
    if elapsed.value_counts().size != 1:
        raise ValueError(
            f"The elapsed time in {timestamp_col} is inconsistent, should be normalized."
        )
    expected = elapsed.dropna().mode()
    expected_delta = expected.iloc[0] if not expected.empty else pd.Timedelta(0)
    # if expected_delta <= pd.Timedelta(0):
    #     raise ValueError("Could not infer a positive sampling interval.")

    last_ts = out[timestamp_col].iloc[-1]
    expected_next_timestamp =  last_ts + expected_delta
    expected_next_timestamp_date = expected_next_timestamp.date()
    expected_next_timestamp_time = expected_next_timestamp.time()
    start_time = start.time()
    
    if respect_weekdays:
        if not respect_time:
            warnings.warn(f"Option respect_weekdays is True and overrides option respect_time. Option respect_time was chosen as False, but changed to True.")
        respect_time = False
        respect_weekdays_and_time = True
    else:
        respect_weekdays_and_time = False

    if respect_time:
        if start_time >= expected_next_timestamp_time:
            # ok, we can append with start_time and expected_next_timestamp_date
            start_new = pd.Timestamp.combine(expected_next_timestamp_date, start_time)
        else:
            # to combine, we need to use start_time and the day after expected_next_timestamp_date
            start_new = pd.Timestamp.combine(expected_next_timestamp_date+pd.Timedelta(days=1), start_time) 

    elif respect_weekdays_and_time:
        start_weekday = start.weekday()
        expected_next_timestamp_weekday = expected_next_timestamp.weekday()
        if start_weekday == expected_next_timestamp_weekday:
            # ok we can append with start_time and expected_next_timestamp_date
            start_new = pd.Timestamp.combine(expected_next_timestamp_date, start_time)
        else:
            # to combine, we need to use start_time, and the closest day after expected_next_timestamp_date respecting start_weekday
            days_delta = (start_weekday - expected_next_timestamp_weekday) % 7 # for a week
            start_day = expected_next_timestamp_date + pd.timedelta(days=days_delta)
            start_new = pd.Timestamp.combine(start_day, start_time)

    else:
        start_new = last_ts + expected_delta # 7h30

    end_new = end-start+start_new
    new_ts = pd.date_range(start=start_new, end=end_new, freq=expected_delta, tz="UTC")

    to_copy[timestamp_col] = new_ts # = pd.DataFrame({timestamp_col: new_ts})
    ### END might be possible to factorize with the same content in copy_median_values

    if start_new != expected_next_timestamp:
        warnings.warn(f"start ({start}) might be incorrectly chosen, it leaves a gap at the end of the extended dataframe. Yields {start_new} instead of {expected_next_timestamp}.")

    expanded = pd.concat([out, to_copy[[timestamp_col, value_col]]], ignore_index=True) 
    return expanded #use len(df) to access the beginning of the expanded part

def copy_median_values(
    df: pd.DataFrame,
    timestamp_col: str,
    value_col: str,
    respect_holidays: bool,
    respect_weekdays: bool,
    respect_time: bool,
    extension,
) -> pd.DataFrame:
    """
    Extend the dataframe by 1 day or 1 week using median values
    computed on group keys (holiday / weekday / time).
    """

    def _parse_extension(value) -> pd.Timedelta:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"jour", "day", "daily"}:
                return pd.Timedelta(days=1)
            if lowered in {"semaine", "week", "weekly"}:
                return pd.Timedelta(days=7)
        raise ValueError("extension must be 'jour' or 'semaine'.")

    def _holiday_flags(ts_series: pd.Series, source_df: pd.DataFrame, mask: pd.Series):
        if "is_holiday" in source_df.columns:
            flags = source_df.loc[mask, "is_holiday"].astype(bool)
            holiday_dates = set(ts_series[flags].dt.date)
            return flags, holiday_dates
        if "activity" in source_df.columns:
            flags = source_df.loc[mask, "activity"].isin(["off", "holidays"])
            holiday_dates = set(ts_series[flags].dt.date)
            return flags, holiday_dates
        if not holiday_dates:
            raise ValueError(
                "respect_holidays=True but no holiday info found. "
                "Provide an 'is_holiday' or 'activity' column."
            )
        flags = ts_series.dt.date.isin(holiday_dates)
        return flags, holiday_dates

    out = df.copy()
    # if timestamp_col not in out.columns:
    #     raise ValueError(f"Missing '{timestamp_col}' in dataframe.")
    # if value_col not in out.columns:
    #     raise ValueError(f"Missing '{value_col}' in dataframe.")

    extension_delta = _parse_extension(extension)

    valid_mask = out[timestamp_col].notna()
    # if not valid_mask.any():
    #     raise ValueError(f"No valid timestamps in '{timestamp_col}'.")

    elapsed = out[timestamp_col].diff()
    if elapsed.value_counts().size != 1:
        raise ValueError(
            f"The elapsed time in {timestamp_col} is inconsistent, should be normalized."
        )
    expected = elapsed.dropna().mode()
    expected_delta = expected.iloc[0] if not expected.empty else pd.Timedelta(0)
    # if expected_delta <= pd.Timedelta(0):
    #     raise ValueError("Could not infer a positive sampling interval.")

    steps = extension_delta / expected_delta
    if not float(steps).is_integer():
        raise ValueError(
            f"Extension '{extension}' does not align with the sampling interval {expected_delta}."
        )
    n_steps = int(steps)

    last_ts = out[timestamp_col].iloc[-1]
    start_new = last_ts + expected_delta
    new_ts = pd.date_range(start=start_new, periods=n_steps, freq=expected_delta)

    group_cols = []
    tmp = pd.DataFrame({timestamp_col: out[timestamp_col], value_col: out[value_col]})

    holiday_dates = set()
    if respect_holidays:
        flags, holiday_dates = _holiday_flags(out[timestamp_col], out, valid_mask)
        tmp["_is_holiday"] = flags
        group_cols.append("_is_holiday")
    if respect_weekdays:
        tmp["_weekday"] = out[timestamp_col].dt.weekday
        group_cols.append("_weekday")
    if respect_time:
        tmp["_hour"] = out[timestamp_col].dt.hour
        tmp["_minute"] = out[timestamp_col].dt.minute
        group_cols.append("_hour")
        group_cols.append("_minute")

    overall_median = tmp[value_col].median()
    if group_cols:
        medians = (
            tmp.groupby(group_cols, dropna=False)[value_col]
            .median()
            .reset_index()
        )

    new_df = pd.DataFrame({timestamp_col: new_ts})
    if respect_holidays:
        if not holiday_dates:
            holiday_dates = set(out[timestamp_col][tmp.get("_is_holiday", False)].dt.date)
        new_df["_is_holiday"] = pd.Series(new_ts).dt.date.isin(holiday_dates)
    if respect_weekdays:
        new_df["_weekday"] = pd.Series(new_ts).dt.weekday
    if respect_time:
        new_df["_hour"] = pd.Series(new_ts).dt.hour
        new_df["_minute"] = pd.Series(new_ts).dt.minute

    if group_cols:
        new_df = new_df.merge(medians, on=group_cols, how="left")
        new_df[value_col] = new_df[value_col].fillna(overall_median)
    else:
        new_df[value_col] = overall_median

    return pd.concat([out, new_df[[timestamp_col, value_col]]], ignore_index=True)


def predict_model(model, X):
    y = pd.Series(model.predict(X), index=X.index)
    return y

def a_priori_knowledge(y):
     y = np.maximum(0., y)
     return y

######### 95% confidence interval
def pred_interval(prediction,y_test,y_fore,alpha=0.95):
    """
    Obtain the prediction interval for each of the prediction
    Input: single prediction, entire test data, test set predictions
    Output: Prediction intervals and the actual prediction
    """
    y_fore = np.array(y_fore)

    # Calculate the sum of squares of the residuals
    err = np.sum(np.square((y_test - y_fore)))

    # Estimate the standard error 
    std = np.sqrt((1 / (y_test.shape[0] - 2)) * err) ## why -2?

    # Compute the z-score
    z = norm.ppf(1 - (1-alpha)/2) # 1.96 for alpha=0.95

    # Calculate the interval
    interval = z*std
    return [prediction-interval,prediction,prediction+interval] 

def confidence_interval(y_test, y_fore):
    prediction_interval = []
    for i in range(y_test.shape[0]):
        prediction_interval.append(pred_interval(y_fore.iloc[i],y_test,y_fore))
    pred_int = pd.DataFrame(prediction_interval,columns=['Lower','Actual','Upper']) 
    return pred_int
