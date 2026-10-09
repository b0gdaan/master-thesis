### main.tex:82  (Аннотация (English abstract))

The topic of the paper is forecasting the inter-market dependencies between traditional financial assets and cryptocurrencies. The focus is on the underlying cryptocurrency, Bitcoin. Traditional assets are: stock indices, precious metals funds and the US dollar index. Ethereum has been used as an additional cryptocurrency to compare results.
A repeatable computer procedure has been developed in which data is retrieved, logarithmic returns are calculated, time-varying correlation targets are formed, properties are constructed, extra-annual estimates of multiple models of machine learning and comparisons with the DCC-GARCH econometric benchmark.
In addition, a practical layer for the formation of an early Risk Signal has been identified, which is intended to alert investors to the stress of the traditional asset market.
The result is that the time-varying intertidal dependence is extra-causally predictable, while the Ridge regression AR(1) and HAR models form a practically inseparable top-ranking group. The above models use an autocorrelation target structure in different ways. Ridge has the lowest average RMSE of 0.0656. Other models significantly exceed the DCC-GARCH rapper. 
The practical signal layer shows moderate results and consequently it makes sense to introduce it as an additional risk detector. It is not intended for the day-to-day determination of the direction of the market.

### chapters/01_uvod.tex:5  (1. Введение)

Bitcoin has gone from a technological experiment to a real asset that is used in their portfolios by professional (institutional) investors and monitored by government agencies. Thus, the task of risk management arises: the previously isolated market has become quite large, attracted huge capital, and market price changes will begin to affect those portfolios in which there is no cryptocurrency at all. The volatility of prices, cryptocurrencies and traditional assets is important for managing risk over time, for this it is important to track the dependence of bitcoin and traditional assets.

### chapters/01_uvod.tex:7  (1. Введение)

This thesis focuses on time-varying intermarket dependence: the work focuses on the changing relationship between bitcoin and traditional assets, stock indexes, gold, silver and the dollar. Is the correlation between cryptocurrencies and traditional assets predictable, and does the price dynamics of cryptocurrencies contain a signal for early warning of changes in the market for traditional assets? The bolder nature of the market movement is more important here than the average level of dependence.

### chapters/01_uvod.tex:9  (1. Введение)

The practical motivation is quite specific. A risk manager does not need an accurate point forecast of profitability to benefit from such an analysis. It is important to be able to recognize the moment when the nature of joint movement changes: when the market regime shifts from uncorrelated to closely related, or when the likelihood of a stressful day in traditional markets increases. Even a modest but statistically reliable signal of this kind can be useful, provided that its limitations are understood.

### chapters/01_uvod.tex:13  (1. Введение)

The thesis is built around two interrelated layers. The first is the task of forecasting: is it possible to predict the sliding correlation between Bitcoin and a traditional asset one step ahead and how machine learning models look against the background of a classical econometric benchmark with a strict out—of-sample assessment. The second is an applied question: is it possible to turn these forecasts into a practical warning signal for the investor.

### chapters/01_uvod.tex:15  (1. Введение)

More specifically, four research questions are addressed:

### chapters/01_uvod.tex:18  (1. Введение)

\item Is the rolling dependency between Bitcoin and conventional assets forecastable out of sample? \item Do machine-learning models outperform a leakage-safe DCC-GARCH benchmark? \item Do machine-learning models add value beyond simple persistence-based baselines such as AR(1)? \item Can crypto-derived dependency forecasts support a practically useful stress-warning signal for conventional markets?

### chapters/01_uvod.tex:26  (1. Введение)

To address these questions, a reproducible Python pipeline was created from scratch. It loads price data, builds log-return series, computes rolling correlations across multiple window lengths, constructs lagged and volatility-based features, and evaluates a range of models within a walk-forward experimental design. The model set includes a naive random-walk baseline and an AR(1) autoregressive model, a Heterogeneous AutoRegressive (HAR) model that uses daily, weekly, and monthly dependency lags, regularised linear models (Ridge, ElasticNet), an adaptive inverse-RMSE-weighted ensemble, tree-based ensembles (Random Forest, GBM, XGBoost), and a leakage-safe DCC-GARCH(1,1) benchmark. On top of the forecasting stage, a second layer converts the forecasts into a binary stress classifier for conventional assets.

### chapters/01_uvod.tex:28  (1. Введение)

The main empirical conclusion: the dependence process is predictable outside the sample, but a significant portion of this predictability comes from the target series’ own history, while new cross-active information adds little. Ridge, AR(1), and HAR rank at the top with virtually identical accuracy because all three rely on the high inertia of moving correlation. The convergence of these three structurally different models speaks for itself: the target series has an almost linear autoregressive structure, and further complicating the model adds almost nothing. At the same time, machine learning offers a clear advantage over DCC-GARCH and is most useful in the task of stress classification, where regularized linear classifiers outperform ensembles based on decision trees.

### chapters/01_uvod.tex:30  (1. Введение)

Three specific contributions follow from this work. First, a reproducible pipeline in Python makes the entire empirical process repeatable—from the input data to the final plots. Second, a systematic comparison of ten models—ranging from naive inertia to XGBoost and DCC-GARCH—within a unified expanding-window framework shows where machine learning offers an advantage and where it does not. Third, explicitly mapping the moving correlation forecasts to a binary stress classifier translates the statistical results into a format suitable for risk management practitioners.

### chapters/01_uvod.tex:34  (1. Введение)

Section 2 reviews the relevant theory and literature: time-varying dependence, financial contagion, machine-learning forecasting methods, and the Diebold--Mariano test. Section 3 describes the data, target construction, feature engineering, model specifications, and the evaluation design. Section 4 presents the empirical results for both layers. Section 5 interprets and qualifies these results. Section 6 concludes.

### chapters/02_teorijske_osnove.tex:5  (2. Теоретические основы)

The way assets move together is central to financial theory, since diversification, contagion, hedging, and portfolio risk all depend on it. The textbook mean-variance framework treats this co-movement as a single constant correlation, but decades of evidence indicate that the static picture does not hold. Empirical correlations drift over time, react more strongly to negative news than to positive news, and rise sharply during market downturns, just when diversification would be most valuable [longin2001]. Forecasting time-varying dependence is therefore of direct practical importance for risk management.
