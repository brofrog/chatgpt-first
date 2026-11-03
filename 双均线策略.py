import numpy as np
import pandas as pd
import talib


def initialize(context):
    """策略初始化函数"""
    # 1. 使用官方规范的 g 全局变量保存策略参数
    g.security = "000001.SZ"
    set_universe([g.security])

    g.short_period = 20  # 短期均线周期
    g.long_period = 60  # 长期均线周期
    g.adx_period = 14  # ADX指标周期

    # 计算历史数据请求长度 (60天均线 + 14天ADX + 平滑预留)
    g.history_count = 100


def handle_data(context, data):
    """盘中逐 Bar/定时触发函数"""
    security = g.security


    # 1. 获取前复权历史 K 线数据（包含 high, low, close）
    df = get_history(
        count=g.history_count,
        frequency="1d",
        field=["high", "low", "close"],
        security_list=[security],
        fq="pre",
    )

    if df.empty or len(df) < g.history_count:
        return

    high_prices = df["high"].values
    low_prices = df["low"].values
    close_prices = df["close"].values

    # 2. 利用 TA-Lib 计算均线 MA20 和 MA60
    ma20 = talib.SMA(close_prices, timeperiod=g.short_period)
    ma60 = talib.SMA(close_prices, timeperiod=g.long_period)

    # 3. 利用 TA-Lib 计算 ADX 与 Directional Indicator (+DI, -DI)
    adx = talib.ADX(
        high_prices, low_prices, close_prices, timeperiod=g.adx_period
    )
    plus_di = talib.PLUS_DI(
        high_prices, low_prices, close_prices, timeperiod=g.adx_period
    )
    minus_di = talib.MINUS_DI(
        high_prices, low_prices, close_prices, timeperiod=g.adx_period
    )

    # 获取最新一帧(-1)与上一帧(-2)的数据，用于判断金叉/死叉及当前ADX状态
    ma20_curr, ma20_prev = ma20[-1], ma20[-2]
    ma60_curr, ma60_prev = ma60[-1], ma60[-2]

    adx_curr = adx[-1]
    plus_di_curr = plus_di[-1]
    minus_di_curr = minus_di[-1]

    # 4. 信号条件判断
    # 均线金叉：20日线向上穿过 60日线
    golden_cross = (ma20_prev <= ma60_prev) and (ma20_curr > ma60_curr)

    # 均线死叉：20日线向下穿过 60日线
    death_cross = (ma20_prev >= ma60_prev) and (ma20_curr < ma60_curr)

    # 方向指标判断 (+DI 是否为正主导，即 +DI > -DI)
    di_is_positive = plus_di_curr > minus_di_curr
    di_is_negative = plus_di_curr < minus_di_curr

    # 买入策略：1. MA20上穿MA60  AND  2. ADX > 25 且 +DI为正(+DI > -DI)
    buy_signal = golden_cross and (adx_curr > 25) and di_is_positive

    # 卖出策略：MA20下穿MA60  OR  (ADX > 40 且 +DI为负)
    sell_signal = death_cross or ((adx_curr > 40) and di_is_negative)

    # 5. 持仓获取与交易执行
    position = get_position(security)
    amount = position.amount if position else 0

    # 触发卖出逻辑
    if sell_signal and amount > 0:
        log.info(
            f"触发卖出信号！当前ADX: {adx_curr:.2f}, +DI: {plus_di_curr:.2f}, -DI: {minus_di_curr:.2f}"
        )
        order_target(security, 0)

    # 触发买入逻辑（全仓买入示例）
    elif buy_signal and amount == 0:
        log.info(
            f"触发买入信号！当前ADX: {adx_curr:.2f}, +DI: {plus_di_curr:.2f}, -DI: {minus_di_curr:.2f}"
        )
        # 获取账户可用资金进行买入
        capital = context.portfolio.cash
        order_target_value(security, capital)