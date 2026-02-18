import pandas as pd
import numpy as np
import pytest #request comes from here

from pytest_csv_params.decorator import csv_params

from ..predict import simple_copy, copy_median_values

# Test data
def expected_res_simple(end, respect_time, respect_weekdays):
    match (end, respect_time, respect_weekdays):
        case ("2026-01-07", False, False):
            to_copy = np.linspace(144, 192, 49) # end is included
            new_ts = pd.date_range("2026-01-26T00:00:00", "2026-01-26T12:00:00", freq="15min", tz="UTC")
        case ("2026-01-07", True, False): # will raise a warning, intended
            to_copy = np.linspace(144, 192, 49)
            new_ts = pd.date_range("2026-01-26T12:00:00", "2026-01-27T00:00:00", freq="15min", tz="UTC")
        case ("2026-01-07", True, True): # will raise a warning, intended
            to_copy = np.linspace(144, 192, 49)
            new_ts = pd.date_range("2026-01-27T12:00:00", "2026-01-28T00:00:00", freq="15min", tz="UTC")
        case ("2026-01-11", False, False):
            to_copy = np.linspace(144, 576, 433)
            new_ts = pd.date_range("2026-01-26T00:00:00", "2026-01-30T12:00:00", freq="15min", tz="UTC")
        case ("2026-01-11", True, False): # will raise a warning, intended
            to_copy = np.linspace(144, 576, 433)
            new_ts = pd.date_range("2026-01-26T12:00:00", "2026-01-31T00:00:00", freq="15min", tz="UTC")
        case ("2026-01-11", True, True): # will raise a warning, intended
            to_copy = np.linspace(144, 576, 433)
            new_ts = pd.date_range("2026-01-27T12:00:00", "2026-02-01T00:00:00", freq="15min", tz="UTC")
        case _:
            raise ValueError(f"Unknown case: ({end}, {respect_time}, {respect_weekdays})")

    return pd.DataFrame({"timestamp_col":new_ts, "value_col":to_copy})
         
def expected_res_median(respect_holidays, respect_weekdays, respect_time, extension): #the correct values are obtained in the excel file "comprendre_test_median.xlsx"
    match (respect_holidays, respect_weekdays, respect_time, extension):
        case (False, False, True, "jour"):
            return pd.Series(np.linspace(960, 1055, 96)) # end is included
        case  (False, True, True, "jour"):
             return pd.Series(np.linspace(672, 767, 96)) #end is included
        case  (False, False, True, "semaine"):
            return pd.Series(np.tile(np.linspace(960, 1055, 96),7)) #end is included
        case  (False, True, True, "semaine"):
            return pd.Series(np.linspace(672, 1343, 96*7)) #end is included
        case _:
            raise ValueError(f"Unknown case: ({respect_holidays}, {respect_weekdays}, {respect_time}, {extension})")

# Mock input data - one value per 15min
@pytest.fixture(scope="function")
def y():
    # mock the input dataframe
    ts = pd.date_range(start="2026-01-05", end="2026-01-26", freq="15min", inclusive="left", tz="UTC")
    val = list(range(len(ts))) # from 0 to 21*24*4 - 1 = 2015 included #end is not included
    y = pd.DataFrame({"timestamp_col":ts, "value_col": val})
    return y

# Write several tests in a few lines
@csv_params(
    data_file="src/tests/simple_copy_test.csv", #only an empty str defines a False
    data_casts={
        "respect_time": bool, "respect_weekdays": bool, # "end", 
    },
)
def test_simple_copy(y, end, respect_time, respect_weekdays):
    # 1. initialise test data   
    starter = "2026-01-06T12:00:00"
    expected_result = expected_res_simple(end, respect_time, respect_weekdays)

    # 2. call function to test
    y_extended = simple_copy(y, 
                              "timestamp_col", 
                              "value_col", 
                              start=pd.Timestamp(starter), 
                              end=end, 
                              source_timezone="Europe/Paris", 
                              respect_time=respect_time,
                              respect_weekdays=respect_weekdays)
    result = y_extended.iloc[len(y):]

    # 3. Assert result, not to test index
    np.array_equal(result.values, expected_result.values)

# Write several tests in a few lines
@csv_params(
    data_file="src/tests/copy_median_value_test.csv", #only an empty str defines a False
    data_casts={
        "respect_holidays": bool, "respect_weekdays": bool, "respect_time": bool, "extension": str,
    },
)
def test_copy_median_values(y, respect_holidays, respect_weekdays, respect_time, extension):
    # 1. initialise test data   
    expected_result = expected_res_median(respect_holidays, respect_weekdays, respect_time, extension)

    # 2. call function to test
    y_extended = copy_median_values(y, 
                              "timestamp_col", 
                              "value_col", 
                              respect_holidays=respect_holidays, 
                              respect_weekdays=respect_weekdays, 
                              respect_time=respect_time, 
                              extension=extension)
    result = y_extended.iloc[len(y):]["value_col"]

    # 3. Assert result
    pd.testing.assert_series_equal(result, expected_result, check_index=False, check_names=False)
