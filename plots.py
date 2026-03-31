import io
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import seaborn as sns
import pandas as pd
import numpy as np
from statsmodels.graphics.tsaplots import plot_pacf, plot_acf
from pathlib import Path


def plot_timeseries(
    df: pd.DataFrame,
):
    ax = df.plot(figsize=(10, 6))

    ax.set_ylabel("Value")
    # ax.set_title(path.name)
    ax.legend(loc="best")
    plt.tight_layout()
    plt.show()


def plot_weekday_seasonal(
        df: pd.DataFrame,
        value_col,
        option_mean= False
):
    if option_mean:
        weekday_means = df.groupby(df.index.dayofweek).mean().reindex(range(7))
        ax = weekday_means.plot(figsize=(10, 6))
    else:
        df["day"] = df.index.dayofweek
        # weekday_means = df.groupby(df.index.dayofweek).mean().reindex(range(7))
        ax = df.plot.scatter(x="day", y=value_col, figsize=(10, 6), alpha=0.4)
    ax.set_xlabel("Weekday")
    ax.set_ylabel(value_col)
    ax.set_xticks(range(7))
    ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.legend(loc="best")
    plt.tight_layout()
    plt.show()      

def seasonal_plot(X, y, period, freq, ax=None, **kwargs):
    if ax is None:
        _, ax = plt.subplots()
    palette = sns.color_palette("husl", n_colors=X[period].nunique(),)
    ax = sns.lineplot(
        x=freq,
        y=y,
        hue=period,
        data=X,
        ax=ax,
        palette=palette,
        legend=False,
        **kwargs,
    )
    ax.set_title(f"Seasonal Plot ({period}/{freq})")
    for line, name in zip(ax.lines, X[period].unique()):
        y_ = line.get_ydata()[-1]
        ax.annotate(
            name,
            xy=(1, y_),
            xytext=(6, 0),
            color=line.get_color(),
            xycoords=ax.get_yaxis_transform(),
            textcoords="offset points",
            size=14,
            va="center",
        )
    return ax

### Simple regression on lag of 1 hour ###
def simple_lag_plot(X_lag_1h, y, y_pred, value_col):

    # lag plot, show relationship of value_col at H and H-1
    fig, ax = plt.subplots()
    ax.plot(X_lag_1h, y, '.', color='0.25')
    ax.plot(X_lag_1h, y_pred)
    ax.set_aspect('equal')
    ax.set_ylabel(value_col)
    ax.set_xlabel('Lag_1')
    ax.set_title(f'Lag Plot of {value_col}')    
    plt.show()

    # show accuracy of forecast cmopared to read data
    ax = y.plot()
    ax = y_pred.plot()

    plt.show()        


### Trend ####
def detect_plot_trend(df, obs_in_window):
    moving_average = df.rolling(
        window=obs_in_window,       # 366-day window
        center=True,      # puts the average at the center of the window
        min_periods=np.floor(obs_in_window/2, casting="unsafe", dtype=int),  # choose about half the window size
    ).mean()              # compute the mean (could also do median, std, min, max, ...)

    ax = df.plot(style=".", color="0.5")
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
        axis=0 # because ts is a series, not an array
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
def autocorrelation_plot(y, value_col):
    _ = plot_acf(y[value_col], lags=7*24) 
    _ = plot_pacf(y[value_col], lags=7*24) 
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
    timestamp_col: str = "timeslot_start_at",
    value_col: str = "conso_gaz_chaudiere_SV4_kWh",
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
        "gap-filled with zeros because the stats info is missing": "tab:brown",
        "considered, not modified, because the stats info is missing": "tab:purple",
        "gap-filled implying modification": "tab:red",
        "gap-filled rest of block because threshold of modification already reached": "tab:pink",
        "gap-filled with 0 because later points already filled at 0": "tab:cyan",
        "modified": "tab:orange",
        "considered, not modified": "tab:green",
        "gap-filled with zero for holidays": "tab:gray",
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

    # display activity
    activity_colors = {
        "active": "tab:blue",
        "off": "tab:red",
        "back_to_work": "tab:green",
        "end_of_work": "tab:orange",
        "holidays": "tab:gray",
    }
    for tag, color in activity_colors.items():
        subset = df[df["activity"] == tag]
        if subset.empty:
            continue
        x_subset = subset[timestamp_col] if timestamp_col in df.columns else subset.index    
        ax.scatter(
            x_subset,
            [-0.05]*len(x_subset),
            s=12,
            alpha=0.8,
            color=color,
        )

    ax.set_ylabel("Value")
    ax.legend(loc="best")
    plt.tight_layout()
    plt.show()

def plot_market_orders(csv_path: Path) -> io.BytesIO:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    df = pd.read_csv(csv_path, sep=";", decimal=".")
    required_cols = [
        "Delivery_datetime(UTC_start_of_period)",
        "Power_in_kW(Sell)",
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    df = df[required_cols]
    df["Delivery_datetime(UTC_start_of_period)"] = pd.to_datetime(
        df["Delivery_datetime(UTC_start_of_period)"],
        errors="coerce",
        utc=True,
        format= "%Y-%m-%d %H:%M:%S"
    )
    df = df.dropna(subset=["Delivery_datetime(UTC_start_of_period)"])
    df = df.set_index("Delivery_datetime(UTC_start_of_period)")

    if df.empty:
        raise ValueError("The df is empty, look for failed timestamp parsing")

    # use Agg, a static backend for this plot to be used in the API
    fig = Figure(figsize=(10, 6))
    FigureCanvasAgg(fig)
    
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(df.index, df["Power_in_kW(Sell)"], label="Power_in_kW(Sell)")
    ax.set_ylabel("Power (kW) (Sell)")
    ax.set_xlabel("Delivery datetime (UTC)")
    ax.legend(loc="best")
    fig.tight_layout()

    image_buffer = io.BytesIO()
    fig.savefig(image_buffer, format="png", dpi=120)
    image_buffer.seek(0)
    return image_buffer
