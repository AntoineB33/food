"""Computes the menu of a day from the foods of the pool (see README.md)."""
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from common import DOSE, amount_step

# What a food of the menu costs, in euros, besides its price: a menu of few foods is quicker to buy and to prepare
FOOD_COST = 0.1
# The least of a food that is worth having in a menu, as a share of its max
LEAST_SHARE = 0.1
# How many of the foods of a saved menu a new menu must not have, when it must differ from the saved ones
DIFFERENT = 3
# What a need out of its range by its whole min or max costs, in euros: when no menu satisfies the needs, the
# closest one to the needs is looked for before the cheapest one
OUT_COST = 1000
# How far inside min and max the totals are aimed, as a share of them: a total that is just on one is counted out
MARGIN = 1e-6
# The seconds given to look for the cheapest menu: the best one found is taken then
TIME_LIMIT = 60


def day_totals(amounts, units, nutrient_db, needs):
    """Returns the total of the day of each need for those amounts ({fdc_id: amount}), in the order of the needs."""
    return [
        sum(
            nutrient_db[fdc_id].get(nutrient_id, 0) * (amount if units[fdc_id] == DOSE else amount / 100)
            for fdc_id, amount in amounts.items() for nutrient_id in need["ids"]
        )
        for need in needs
    ]


def solve_menu(foods, nutrient_db, needs, limits, prices, forced=(), others=(), strict=True):
    """Returns the cheapest menu of those foods that satisfies the needs, as {fdc_id: amount}, None without any.

    foods is a list of (fdc_id, unit), limits the least and the most of each one in a day ({fdc_id: (min, max)}, the
    max being given), prices what one gram or one dose of each one costs. A food that is in the menu has at least
    its min, or else LEAST_SHARE of its max. The forced foods are in the menu. others are the foods of other menus:
    the menu lacks at least DIFFERENT foods of each one. Without strict, the needs that no menu satisfies are left
    out of their range, by as little as possible.
    """
    needs = [need for need in needs if need["min"] > 0 or need["max"] is not None]
    count, kept = len(foods), len(needs)
    most = np.array([limits[fdc_id][1] for fdc_id, _ in foods])
    steps = np.array([amount_step(limit, unit) for (_, unit), limit in zip(foods, most)])
    least = np.array([max(limits[fdc_id][0] or 0, LEAST_SHARE * limit) for (fdc_id, _), limit in zip(foods, most)])
    # In steps: a food that is in the menu has at least one
    most = np.maximum(np.floor(most / steps + 1e-9), 1)
    least = np.minimum(np.maximum(np.ceil(least / steps - 1e-9), 1), most)

    # The unknowns: for each food, its amount as a number of steps, then whether it is in the menu. Then for each
    # need, how far the total is under its min and over its max, as a share of them
    size = 2 * count + 2 * kept
    rows, lower, upper = [], [], []
    for index, need in enumerate(needs):
        # What one step of each food brings: the nutrients are given for 100g of a food, or for one dose
        brought = [
            sum(nutrient_db[fdc_id].get(nutrient_id, 0) for nutrient_id in need["ids"]) * (1 if unit == DOSE else 0.01)
            for fdc_id, unit in foods
        ]
        # Every need is counted as a share of its max, or else of its min: their units are very different
        scale = need["max"] or need["min"]
        row = np.zeros(size)
        row[:count] = np.array(brought) * steps / scale
        row[2 * count + index] = need["min"] / scale
        row[2 * count + kept + index] = -(need["max"] or 0) / scale
        rows.append(row)
        lower.append(need["min"] * (1 + MARGIN) / scale if need["min"] > 0 else -np.inf)
        upper.append(np.inf if need["max"] is None else need["max"] * (1 - MARGIN) / scale)
    for index in range(count):
        # A food that is not in the menu has no amount, one that is has between its least and its most
        for bound, low, high in ((most[index], -np.inf, 0), (least[index], 0, np.inf)):
            row = np.zeros(size)
            row[index], row[count + index] = 1, -bound
            rows.append(row)
            lower.append(low)
            upper.append(high)
    ids = [fdc_id for fdc_id, _ in foods]
    for other in others:
        shared = [index for index, fdc_id in enumerate(ids) if fdc_id in other]
        # A menu that has foods out of the pool cannot be found again anyway
        if len(shared) == len(other) and len(shared) > DIFFERENT:
            row = np.zeros(size)
            row[[count + index for index in shared]] = 1
            rows.append(row)
            lower.append(-np.inf)
            upper.append(len(shared) - DIFFERENT)

    cost = np.concatenate([
        np.array([prices[fdc_id] for fdc_id in ids]) * steps, np.full(count, FOOD_COST), np.full(2 * kept, OUT_COST),
    ])
    bounds = Bounds(
        np.concatenate([np.zeros(count), np.array([1 if fdc_id in forced else 0 for fdc_id in ids]), np.zeros(2 * kept)]),
        np.concatenate([most, np.ones(count), np.full(2 * kept, 0 if strict else np.inf)]),
    )
    result = milp(
        cost, constraints=LinearConstraint(np.array(rows), lower, upper), bounds=bounds,
        integrality=np.concatenate([np.ones(2 * count), np.zeros(2 * kept)]), options={"time_limit": TIME_LIMIT},
    )
    if result.x is None:
        return None
    return {
        fdc_id: round(float(number) * float(step), 1)
        for fdc_id, number, step in zip(ids, np.round(result.x[:count]), steps) if number > 0
    }
