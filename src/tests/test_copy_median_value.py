import pandas as pd
import numpy as np
import pytest #request comes from here

from pytest_csv_params.decorator import csv_params

from ..predict import copy_median_values

# Test data
def expected_res(use_holidays, use_weekdays, use_time, extension): #the correct values are obtained in the excel file "comprendre_test_median.xlsx"
    match (use_holidays, use_weekdays, use_time, extension):
        case (False, False, True, "jour"):
            return pd.Series(np.linspace(960, 1055, 96)) # end is included
        case  (False, True, True, "jour"):
             return pd.Series(np.linspace(672, 767, 96)) #end is included
        case  (False, False, True, "semaine"):
            return pd.Series(np.tile(np.linspace(960, 1055, 96),7)) #end is included
        case  (False, True, True, "semaine"):
            return pd.Series(np.linspace(672, 1343, 96*7)) #end is included
        case _:
            raise ValueError(f"Unknown case: ({use_holidays}, {use_weekdays}, {use_time}, {extension})")

# Mock input data - one value per 15min
@pytest.fixture(scope="function")
def y():
    # mock the input dataframe
    ts = pd.date_range(start="2026-01-05", end="2026-01-26", freq="15min", inclusive="left")
    val = list(range(len(ts))) # from 0 to 21*24*4 - 1 = 2015 included #end is not included
    y = pd.DataFrame({"timestamp_col":ts, "value_col": val})
    return y

# Write several tests in a few lines
@csv_params(
    data_file="src/tests/copy_median_value_test.csv", #only an empty str defines a False
    data_casts={
        "use_holidays": bool, "use_weekdays": bool, "use_time": bool, "extension": str,
    },
)
def test_copy_median_values(y, use_holidays, use_weekdays, use_time, extension):
    # 1. initialise test data   
    expected_result = expected_res(use_holidays, use_weekdays, use_time, extension)

    # 2. call function to test
    y_extended = copy_median_values(y, 
                              "timestamp_col", 
                              "value_col", 
                              use_holidays=use_holidays, 
                              use_weekdays=use_weekdays, 
                              use_time=use_time, 
                              extension=extension)
    result = y_extended.iloc[len(y):]["value_col"]

    # 3. Assert result
    pd.testing.assert_series_equal(result, expected_result, check_index=False, check_names=False)


if __name__ == '__main__':
    test_copy_median_values()
