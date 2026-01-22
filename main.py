from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from statsmodels.graphics.tsaplots import plot_pacf, plot_acf
import seaborn as sns
from statsmodels.tsa.deterministic import DeterministicProcess, Seasonality
from sklearn.linear_model import LinearRegression

def input_csv(
    csv_path: str = r"C:\Users\Loris Amabile\Documents\france champignon debut ML timeseries kaggle\données_bonduelle.csv",
):
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path, sep=";", decimal=",")

    return df

def parse_date_col(
    df: pd.DataFrame,
    date_col: str | None = None,
):
    if date_col is None:
        # Heuristic: pick the first column that parses as datetime well
        for col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            if parsed.notna().mean() > 0.8:
                date_col = col
                df[col] = parsed
                break

    if not date_col:
        raise ValueError("Could not infer date column.")

    df = df.sort_values(date_col).set_index(date_col)
    y = df.select_dtypes(include="number")

    if y.empty:
        raise ValueError("No numeric columns found to plot.")
        
    return y

def plot_timeseries_csv(
    y: pd.DataFrame,
):
    ax = y.plot(figsize=(10, 6))

    ax.set_ylabel("Value")
    # ax.set_title(path.name)
    ax.legend(loc="best")
    plt.tight_layout()
    plt.show()


def plot_weekday_seasonal_csv(
        y: pd.DataFrame,
        option_mean= False
):
    if option_mean:
        weekday_means = y.groupby(y.index.dayofweek).mean().reindex(range(7))
        ax = weekday_means.plot(figsize=(10, 6))
        ax.set_xlabel("Weekday")
        ax.set_ylabel("Mean value")
        # ax.set_title(f"{path.name} (Weekday seasonal plot)")
        ax.set_xticks(range(7))
        ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        ax.legend(loc="best")
        plt.tight_layout()
        plt.show()
    else:
        y["day"] = y.index.dayofweek
        # weekday_means = y.groupby(y.index.dayofweek).mean().reindex(range(7))
        ax = y.plot.scatter(x="day", y="MWh use", figsize=(10, 6), alpha=0.4)
        ax.set_xlabel("Weekday")
        ax.set_ylabel("MWh use")
        ax.set_xticks(range(7))
        ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        ax.legend(loc="best")
        plt.tight_layout()
        plt.show()        

def data_workflow():
    df = input_csv()
    y = parse_date_col(df)
    return y

def plot_workflow(y):
    plot_timeseries_csv(y)
    plot_weekday_seasonal_csv(y)

### Simple regression on lag of 1 hour ###
def simple_lag(steam_cons):
    # simple lag
    steam_cons['Lag_1'] = steam_cons['MWh use'].shift(1)
    steam_cons.head()    


    X = steam_cons.loc[:, ['Lag_1']]
    X.dropna(inplace=True)  # drop missing values in the feature set
    y = steam_cons.loc[:, 'MWh use']  # create the target
    y, X = y.align(X, join='inner')  # drop corresponding values in target

    model = LinearRegression()
    model.fit(X, y)

    y_pred = pd.Series(model.predict(X), index=X.index)

    # lag plot, show relationship of MWh use at H and H-1
    fig, ax = plt.subplots()
    ax.plot(X['Lag_1'], y, '.', color='0.25')
    ax.plot(X['Lag_1'], y_pred)
    ax.set_aspect('equal')
    ax.set_ylabel('MWh use')
    ax.set_xlabel('Lag_1')
    ax.set_title('Lag Plot of MWH use');    
    plt.show()

    # show accuracy of forecast cmopared to read data
    ax = y.plot()
    ax = y_pred.plot()

    plt.show()

# ### Trend ####
# def detect_plot_trend(y, obs_in_window):
#     moving_average = y.rolling(
#         window=obs_in_window,       # 366-day window
#         center=True,      # puts the average at the center of the window
#         min_periods=np.floor(obs_in_window/2, casting="unsafe", dtype=int),  # choose about half the window size
#     ).mean()              # compute the mean (could also do median, std, min, max, ...)

#     ax = y.plot(style=".", color="0.5")
#     moving_average.plot(
#         ax=ax, linewidth=3, title=f"France champignon Conso - {obs_in_window} obs for Moving Average", legend=False,
#     )
#     plt.tight_layout()
#     plt.show()

#     # CCL: no trend 
# ###


#### Seasonality #####
def plot_periodogram(ts, detrend=None, ax=None):
    from scipy.signal import periodogram
    fs = pd.Timedelta("366D") / pd.Timedelta("1h") # donne 8784 observations
    frequencies, spectrum = periodogram(
        ts,
        fs=fs,
        detrend=detrend,
        window="boxcar",
        scaling='spectrum',
        axis=0 # because y is a series, not an array
    )
    if ax is None:
        _, ax = plt.subplots()
    ax.step(frequencies, spectrum, color="purple")
    ax.set_xscale("log")
    ax.set_xticks([1, 2, 4, 6, 12, 26, 52, 104])
    ax.set_xticklabels(
        [
            "Annual (1)",
            "Semiannual (2)",
            "Quarterly (4)",
            "Bimonthly (6)",
            "Monthly (12)",
            "Biweekly (26)",
            "Weekly (52)",
            "Semiweekly (104)",
        ],
        rotation=30,
    )
    ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    ax.set_ylabel("Variance")
    ax.set_title("Periodogram")
    plt.tight_layout()
    plt.show()

def lagplot(x, y=None, lag=1, standardize=False, ax=None, **kwargs):
    from matplotlib.offsetbox import AnchoredText
    x_ = x.shift(lag)
    if standardize:
        x_ = (x_ - x_.mean()) / x_.std()
    if y is not None:
        y_ = (y - y.mean()) / y.std() if standardize else y
    else:
        y_ = x
    corr = y_.corr(x_)
    if ax is None:
        fig, ax = plt.subplots()
    scatter_kws = dict(
        alpha=0.75,
        s=3,
    )
    line_kws = dict(color='C3', )
    ax = sns.regplot(x=x_,
                     y=y_,
                     scatter_kws=scatter_kws,
                     line_kws=line_kws,
                     lowess=True,
                     ax=ax,
                     **kwargs)
    at = AnchoredText(
        f"{corr:.2f}",
        prop=dict(size="large"),
        frameon=True,
        loc="upper left",
    )
    at.patch.set_boxstyle("square, pad=0.0")
    ax.add_artist(at)
    ax.set(title=f"Lag {lag}", xlabel=x_.name, ylabel=y_.name)
    return ax

def plot_lags(x, y=None, lags=6, nrows=1, lagplot_kwargs={}, **kwargs):
    import math
    kwargs.setdefault('nrows', nrows)
    kwargs.setdefault('ncols', math.ceil(lags / nrows))
    kwargs.setdefault('figsize', (kwargs['ncols'] * 2, nrows * 2 + 0.5))
    fig, axs = plt.subplots(sharex=True, sharey=True, squeeze=False, **kwargs)
    for ax, k in zip(fig.get_axes(), range(kwargs['nrows'] * kwargs['ncols'])):
        if k + 1 <= lags:
            ax = lagplot(x, y, lag=k + 1, ax=ax, **lagplot_kwargs)
            ax.set_title(f"Lag {k + 1}", fontdict=dict(fontsize=14))
            ax.set(xlabel="", ylabel="")
        else:
            ax.axis('off')
    plt.setp(axs[-1, :], xlabel=x.name)
    plt.setp(axs[:, 0], ylabel=y.name if y is not None else x.name)
    fig.tight_layout(w_pad=0.1, h_pad=0.1)
    return fig

def make_lags(ts, lags):
    return pd.concat(
        {
            f'y_lag_{i}': ts.shift(i)
            for i in range(1, lags + 1)
        },
        axis=1)



if __name__ == "__main__":
    steam_cons = data_workflow()
    # give information on the frequency of the index:
    steam_cons = steam_cons.asfreq('h')
    
    # complex lags
    # X = make_lags(steam_cons["MWh use"], lags=27)
    # X = X.fillna(0.0)    

    # seasonality: create the feature set
    dp = DeterministicProcess(
        index=steam_cons.index,  # dates from the training data
        constant=True,       # dummy feature for the bias (y_intercept)
        additional_terms=[Seasonality(period=24*7)],  # 168 hour-of-week dummies
        seasonal=True,       # seasonality (based on the frequency of the data. hourly data->24-hour cycle)
        drop=True,           # drop terms if necessary to avoid collinearity
    )
    # `in_sample` creates features for the dates given in the `index` argument
    X = dp.in_sample()

    X.head()    

    # seasonality: fit the model
    y = steam_cons["MWh use"] # the target

    model = LinearRegression(fit_intercept=False)
    model.fit(X, y)

    y_pred = pd.Series(model.predict(X), index=y.index)
    X_fore = dp.out_of_sample(steps=96)
    y_fore = pd.Series(model.predict(X_fore), index=X_fore.index)

    ax = y.plot(color='0.25', style='.', title="Steam consumption")
    ax = y_pred.plot(ax=ax, label="Seasonal")
    ax = y_fore.plot(ax=ax, label="Seasonal Forecast", color='C3')
    _ = ax.legend()
    plt.show()