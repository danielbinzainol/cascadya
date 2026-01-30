import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from statsmodels.graphics.tsaplots import plot_pacf, plot_acf


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


### Simple regression on lag of 1 hour ###
def simple_lag_plot(X, y, y_pred):

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


### Trend ####
def detect_plot_trend(y, obs_in_window):
    moving_average = y.rolling(
        window=obs_in_window,       # 366-day window
        center=True,      # puts the average at the center of the window
        min_periods=np.floor(obs_in_window/2, casting="unsafe", dtype=int),  # choose about half the window size
    ).mean()              # compute the mean (could also do median, std, min, max, ...)

    ax = y.plot(style=".", color="0.5")
    moving_average.plot(
        ax=ax, linewidth=3, title=f"France champignon Conso - {obs_in_window} obs for Moving Average", legend=False,
    )
    plt.tight_layout()
    plt.show()

    # CCL: no trend 
###    

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

# Autocorrelation
def autocorrelation_plot(y):
    _ = plot_acf(y["MWh use"], lags=7*24) 
    _ = plot_pacf(y["MWh use"], lags=7*24) 
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

def cool_plot(y, y_fore, pred_int, y_pred):
    ax = y.plot(color='0.25', style='.', title="Steam consumption")
    ax = y_pred.plot(ax=ax, label="Seasonal")
    ax = y_fore.plot(ax=ax, label="Seasonal Forecast", color='C3')
    plt.fill_between(y_fore.index,pred_int['Lower'],pred_int['Upper'],label='Forecast Interval',color="tab:blue",alpha=0.2)
    _ = ax.legend()
    plt.show()


def plot_gap_filled_timeseries(
    df: pd.DataFrame,
    timestamp_col: str = "Valeur mesurée le",
    value_col: str = "MWh use",
    tag_col: str = "tag",
):
    if tag_col not in df.columns:
        raise ValueError(f"Missing '{tag_col}' column for gap-filled plot.")

    if timestamp_col in df.columns:
        x = df[timestamp_col]
    else:
        x = df.index

    plt.ion() # to enable to see the figure without blocking the shell
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(x, df[value_col], color="0.8", linewidth=1, label="series")

    tag_colors = {
        "original": "tab:blue",
        "gap-filled": "tab:red",
        "modified": "tab:orange",
        "considered, not modified": "tab:green",
    }
    for tag, color in tag_colors.items():
        subset = df[df[tag_col] == tag]
        if subset.empty:
            continue
        x_subset = subset[timestamp_col] if timestamp_col in df.columns else subset.index
        ax.scatter(
            x_subset,
            subset[value_col],
            s=12,
            alpha=0.8,
            color=color,
            label=tag,
        )

    ax.set_ylabel("Value")
    ax.legend(loc="best")
    plt.tight_layout()
    plt.show()
