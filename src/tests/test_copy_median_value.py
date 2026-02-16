import pandas as pd
import pytest

from ..predict import copy_median_values

# one value per day
@pytest.fixture(scope="function")
def y():
    # mock the input dataframe
    ts = pd.date_range(start="2026-01-05", end="2026-01-25")
    val = list(range(21)) # from 0 to 20
    y = pd.DataFrame({"timestamp_col":ts, "value_col": val})
    return y

def test_copy_median_values_jour_hours(y):   
    y_extended = copy_median_values(y, 
                              "timestamp_col", 
                              "value_col", 
                              use_holidays=False, 
                              use_weekdays=False, 
                              use_hours=True, 
                              extension="jour")
    
    assert y_extended.iloc[-1]["value_col"] == 10

def test_copy_median_values_jour_weekdays(y):   
    y_extended = copy_median_values(y, 
                              "timestamp_col", 
                              "value_col", 
                              use_holidays=False, 
                              use_weekdays=True, 
                              use_hours=True, 
                              extension="jour")
    
    assert y_extended.iloc[-1]["value_col"] == 7

def test_copy_median_values_semaine_hours(y):   
    y_extended = copy_median_values(y, 
                              "timestamp_col", 
                              "value_col", 
                              use_holidays=False, 
                              use_weekdays=True, 
                              use_hours=True, 
                              extension="semaine")
    
    expected = pd.Series([7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0])
    print(expected)
    print(y_extended.iloc[len(y):]["value_col"])
    pd.testing.assert_series_equal(y_extended.iloc[len(y):]["value_col"], expected, check_index=False, check_names=False)

def test_copy_median_values_semaine_weekdays(y):   
    y_extended = copy_median_values(y, 
                              "timestamp_col", 
                              "value_col", 
                              use_holidays=False, 
                              use_weekdays=True, 
                              use_hours=True, 
                              extension="semaine")
    
    expected = pd.Series([7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0])
    print(expected)
    print(y_extended.iloc[len(y):]["value_col"])
    pd.testing.assert_series_equal(y_extended.iloc[len(y):]["value_col"], expected, check_index=False, check_names=False)


if __name__ == '__main__':
    test_copy_median_values_jour_hours()
    test_copy_median_values_jour_weekdays()
    test_copy_median_values_semaine_hours()
    test_copy_median_values_semaine_weekdays()

