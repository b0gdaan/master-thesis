# Defense Script

## 7-10 Minute Structure

### 1. Opening

Good afternoon.

My master's thesis is titled:
Forecasting Time-Varying Intermarket Dependencies Between Cryptocurrencies and Conventional Assets Using Machine Learning.

The core idea of this research is that cryptocurrencies, and Bitcoin in particular, may contain useful information not only about themselves, but also about changing relationships with conventional assets such as stock indices, precious metals, and the U.S. dollar index.

### 2. Research Problem

The main research question is:
Can Bitcoin-based information help forecast time-varying intermarket dependency with conventional assets, and can that information be translated into an early warning signal for investors?

This question has two layers.

The first layer is scientific:
Is the dependency between crypto and traditional markets forecastable?

The second layer is practical:
Can that forecast help an investor recognize periods of elevated market risk earlier?

### 3. Data and Assets

The empirical study uses daily data.
Bitcoin is treated as the base cryptocurrency.
The conventional asset universe includes:
- S&P 500
- NASDAQ Composite
- Gold ETF
- Silver ETF
- U.S. Dollar Index proxy
- Ethereum as an additional crypto reference asset

The data are transformed into logarithmic returns.
The target is not next-day price directly, but a rolling time-varying correlation between Bitcoin and each conventional asset.

### 4. Methodology

The methodology has two stages.

Stage one is dependency forecasting.
I compute rolling correlations using multiple window lengths: 14, 30, 60, and 90 days.
Then I apply the Fisher transformation and forecast the next value of that dependency series.

The forecasting models include:
- Naive persistence
- AR(1)
- Ridge
- Elastic Net
- Random Forest
- Gradient Boosting
- XGBoost
- DCC-GARCH as the econometric benchmark

All experiments are evaluated in a walk-forward framework to avoid look-ahead bias.
A separate leakage-safe DCC walk-forward benchmark was implemented for methodological correctness.

Stage two is the investor signal layer.
Here, the best dependency forecast and crypto-derived features are used to predict stress days in conventional assets.
This is framed as a risk-warning task rather than a pure daily up/down trading rule.

### 5. Main Results

The first main result is that time-varying dependency is forecastable.
So the problem is meaningful and not random.

The second main result is that the strongest predictive force is persistence in the dependency series itself.
This is why, on average, AR(1) and Naive Last perform best.

The third result is that machine-learning models frequently outperform the DCC-GARCH benchmark, but usually do not outperform the strongest simple persistence baselines on average.

The fourth result is that the investor signal layer produces moderate but meaningful results.
It is most useful as a risk-management overlay, especially for equity-related markets, rather than as a standalone market timing engine.

### 6. Scientific Contribution

The scientific contribution of the thesis is threefold.

First, it provides a reproducible pipeline for forecasting time-varying intermarket dependencies between Bitcoin and conventional assets.

Second, it offers a fair out-of-sample comparison between machine-learning models, simple persistence baselines, and a leakage-safe DCC-GARCH benchmark.

Third, it extends the analysis from pure dependency forecasting to an investor-oriented early warning framework.

### 7. Practical Contribution

The practical value of the work is not that it predicts every next-day market movement perfectly.
That would be an unrealistic claim.

Its practical value is that crypto information can help detect changes in market structure and can contribute to earlier identification of elevated risk conditions.

So the model should be interpreted as a support tool for risk management and exposure reduction, not as a guaranteed trading oracle.

### 8. Conclusion

In conclusion, the thesis shows that Bitcoin-related information carries meaningful information about changing intermarket dependency with conventional assets.
That dependency can be forecasted.
And although the practical signal is moderate, it is sufficiently informative to justify further research and possible use as a supplementary risk-warning mechanism.

Thank you.

## Short Version If They Ask For 3 Minutes

My thesis studies whether Bitcoin contains information about changing relationships with conventional assets such as equities, metals, and the dollar index.

I model these relationships as time-varying rolling dependencies and forecast them using machine learning, simple baselines, and a leakage-safe DCC-GARCH benchmark.

The main result is that these dependencies are forecastable, but most predictive power comes from persistence in the dependency series itself, which is why simple AR(1)-type models often perform best.

Machine learning still improves upon DCC-GARCH in many cases, and a second investor-oriented layer transforms the forecasts into an early warning signal for stress days.

So the contribution of the thesis is both scientific and practical: it shows that crypto data can help forecast changing market structure and can support risk management, even if it does not perfectly predict every next-day market move.

## Likely Questions and Good Answers

### Why are simple models better than complex ones?

Because the target is a rolling dependency series, and such series are highly persistent.
So the strongest forecasting information is already contained in the recent value of the target itself.
That is not a failure of the research.
It is an important empirical result about the structure of the problem.

### Does this mean machine learning is useless here?

No.
Machine learning is still useful because it improves upon the DCC-GARCH benchmark in many settings and helps test whether nonlinear information exists.
The result is that machine learning adds value, but mostly as an incremental improvement rather than a complete replacement of persistence baselines.

### Can an investor directly trade this model?

Not as a standalone system in its current form.
The investor signal is better interpreted as a risk overlay.
It can help identify periods of elevated stress probability, but it should complement, not replace, broader portfolio and macro analysis.

### Why did you use rolling correlation instead of direct return prediction?

Because the topic of the thesis is intermarket dependency, not just direction prediction.
Rolling correlation gives a direct representation of how the relationship between markets changes over time.
That is more aligned with the scientific objective.
The investor signal layer was then added to connect the academic result with practical use.

### Why is DCC-GARCH weaker here?

Because the thesis evaluates it in a strict walk-forward framework and compares it on a one-step-ahead smoothed dependency target.
In this setup, DCC-GARCH is less flexible than some alternatives and does not exploit persistence as efficiently as simple baselines.

### What is the main limitation of the thesis?

The main limitations are daily frequency, one-step horizon, and the fact that the signal layer is not yet embedded into a full transaction-cost-aware portfolio backtest.
Those are natural next steps for future work.
