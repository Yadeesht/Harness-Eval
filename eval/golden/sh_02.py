"""sh_02: delete the >1,00,000 rule, then set the other amount rule to 50,000 (indices shift)."""

import re

from _lib import js, pick


def _rules(info: str) -> list[tuple[int, str, str]]:
    """(index, condition, values) for the Line Items rules in get_spreadsheet_info output."""
    block = js(info)["message"].split('Conditional formats for "Line Items"')[1]
    return [(int(i), cond, vals) for i, cond, vals in re.findall(r"\[(\d+)\] (\w+) values=\[(.*?)\]", block)]


async def golden(t):
    sid = pick(js(await t("list_spreadsheets"))["spreadsheets"], name="Platform Budget 2026")["id"]
    rules = _rules(await t("get_spreadsheet_info", spreadsheet_id=sid))
    over_lakh = next(i for i, cond, vals in rules if cond == "NUMBER_GREATER" and "100000" in vals)
    await t("delete_conditional_formatting", spreadsheet_id=sid, rule_index=over_lakh, sheet_name="Line Items")
    rules = _rules(await t("get_spreadsheet_info", spreadsheet_id=sid))
    other = next(i for i, cond, vals in rules if cond == "NUMBER_GREATER")
    await t("update_conditional_formatting", spreadsheet_id=sid, rule_index=other, sheet_name="Line Items", condition_values=["50000"])
    return "Deleted the rule highlighting amounts over ₹1,00,000 and changed the remaining amount rule to > 50,000, keeping its yellow fill."


async def negative(t):
    """Trap taken: delete [0], then update [1] using the old numbering (hits the custom-formula rule)."""
    sid = pick(js(await t("list_spreadsheets"))["spreadsheets"], name="Platform Budget 2026")["id"]
    await t("get_spreadsheet_info", spreadsheet_id=sid)
    await t("delete_conditional_formatting", spreadsheet_id=sid, rule_index=0, sheet_name="Line Items")
    await t("update_conditional_formatting", spreadsheet_id=sid, rule_index=1, sheet_name="Line Items", condition_values=["50000"])
    return "Done."
