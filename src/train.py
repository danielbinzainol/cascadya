import pandas as pd
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.deterministic import DeterministicProcess, Seasonality
import holidays

#
from src.utils import load_config


def model_choice(model_name):
        model_map = {
            'LinearRegression': LinearRegression,
            # 'DecisionTreeClassifier': DecisionTreeClassifier,
            # 'GradientBoostingClassifier': GradientBoostingClassifier
        }
    
        config = load_config()
        model_params = config["models"][model_name]["params"]

        model_class = model_map[model_name]
        model = model_class(**model_params)    

        return model

def make_lags(ts, lags):
    return pd.concat(
        {
            f'y_lag_{i}': ts.shift(i)
            for i in range(1, lags + 1)
        },
        axis=1)

def create_feature(y):
    # seasonality: create the feature set
    dp = DeterministicProcess(
        index=y.index,  # dates from the training data
        constant=True,       # dummy feature for the bias (y_intercept)
        additional_terms=[Seasonality(period=24*7)],  # 168 hour-of-week dummies
        drop=True,           # drop terms if necessary to avoid collinearity
    )
    # `in_sample` creates features for the dates given in the `index` argument
    X = dp.in_sample()

    # add lags
    X_lags = make_lags(y, lags=168)[["y_lag_1", "y_lag_24", "y_lag_168"]]
    X = pd.concat([X, X_lags], axis=1).dropna()

    # add holidays knowledge
    fr_holidays = holidays.FR(years=2025)
    holiday_dates = set(fr_holidays.keys())
    X["holidays"] = pd.Index(X.index.date).isin(holiday_dates)

    return X

def train_model(model, X_train, y_train):
    model.fit(X_train, y_train)
