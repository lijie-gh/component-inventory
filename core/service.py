# -*- coding: utf-8 -*-
"""业务服务层：元件入账、出入库、盘点、刷新、预警。

把所有业务规则集中在这里，界面层只负责调用，方便以后换界面（Web / 命令行）。
"""
import os

from . import config, db, lcsc


class ServiceError(Exception):
    pass


# ---------------------------------------------------------------- 入账
def add_from_lcsc(code, quantity=0, location=None, extra=None, operator=""):
    """通过嘉立创 C 号添加元件（自动联网抓取资料）。

    返回 (part_id, info, 是否新建)。
    """
    location = (location or config.DEFAULT_LOCATION).strip() or config.DEFAULT_LOCATION
    code = lcsc._normalize_code(code)
    if not lcsc.is_lcsc_code(code):
        raise ServiceError(f"“{code}”不是有效的嘉立创 C 号（形如 C1525）")

    data = lcsc.fetch_part(code)

    # 网络请求放在事务外（不能长时间占着写锁），之后的所有写库动作一次性提交
    with db.transaction():
        exist = db.get_part_by_code(code)
        if exist:
            pid = exist["id"]
            patch = {k: v for k, v in data.items()
                     if not k.startswith("_") and v not in (None, "")}
            patch["last_fetch"] = config.now_str()
            if extra:
                patch.update({k: v for k, v in extra.items() if v not in (None, "")})
            patch.pop("source", None)
            db.update_part(pid, patch)
            is_new = False
        else:
            payload = {k: v for k, v in data.items() if not k.startswith("_")}
            payload["last_fetch"] = config.now_str()
            payload["supplier"] = payload.get("supplier") or "嘉立创商城"
            if extra:
                payload.update({k: v for k, v in extra.items() if v not in (None, "")})
            pid = db.add_part(payload, location=location, quantity=0)
            is_new = True

        qty = int(quantity or 0)
        if qty:
            db.change_stock(pid, location, qty)
            db.add_txn(pid, config.TXN_IN, qty, location, operator,
                       "新建元件入账" if is_new else "追加入库")
    return pid, data, is_new


def add_manual(data, quantity=0, location=None, operator=""):
    """添加非嘉立创渠道采购的元件（手工录入，不联网）。

    返回 (part_id, 是否新建)。
    """
    location = (location or config.DEFAULT_LOCATION).strip() or config.DEFAULT_LOCATION
    payload = dict(data or {})
    payload["source"] = config.SOURCE_OTHER
    payload.setdefault("unit", "个")
    if not (payload.get("name") or payload.get("model")):
        raise ServiceError("至少填写“名称/描述”或“型号”")

    with db.transaction():
        code = (payload.get("code") or "").strip().upper()
        exist = None
        if code:
            exist = db.get_part_by_code(code)
        if not exist and payload.get("model"):
            exist = db.query_one("SELECT * FROM parts WHERE model=? AND source=?",
                                 (payload["model"], config.SOURCE_OTHER))
        if not exist and payload.get("name"):
            exist = db.query_one("SELECT * FROM parts WHERE name=? AND source=?",
                                 (payload["name"], config.SOURCE_OTHER))

        qty = int(quantity or 0)
        if exist:
            pid = exist["id"]
            patch = {k: v for k, v in payload.items() if v not in (None, "")}
            patch.pop("source", None)
            db.update_part(pid, patch)
            is_new = False
        else:
            pid = db.add_part(payload, location=location, quantity=0)
            is_new = True

        if qty:
            db.change_stock(pid, location, qty)
            db.add_txn(pid, config.TXN_IN, qty, location, operator,
                       "手工入账（其它渠道）" if is_new else "追加入库")
    return pid, is_new


def add_from_row(data, quantity=0, location=None, operator="", note="表格导入"):
    """用表格里已有的资料入账（不联网）。

    有 C 号的归入「嘉立创件」，没有的归入「其它渠道件」；已有记录则更新资料
    并追加库存。用于批量导入时不想逐条联网查询的场景。
    """
    location = (location or config.DEFAULT_LOCATION).strip() or config.DEFAULT_LOCATION
    payload = {k: v for k, v in dict(data or {}).items() if v not in (None, "")}
    code = (payload.get("code") or "").strip().upper()
    if code:
        payload["code"] = code
        payload["source"] = config.SOURCE_LCSC
        payload["supplier"] = payload.get("supplier") or "嘉立创商城"
    else:
        payload["source"] = config.SOURCE_OTHER
    payload.setdefault("unit", "个")
    if not (payload.get("name") or payload.get("model")):
        raise ServiceError("这一行没有名称或型号，无法入账")

    with db.transaction():
        exist = None
        if code:
            exist = db.get_part_by_code(code)
        elif payload.get("model"):
            exist = db.query_one("SELECT * FROM parts WHERE model=? AND source=?",
                                 (payload["model"], config.SOURCE_OTHER))
        if not exist and not code and payload.get("name"):
            exist = db.query_one("SELECT * FROM parts WHERE name=? AND source=?",
                                 (payload["name"], config.SOURCE_OTHER))

        qty = int(quantity or 0)
        if exist:
            pid = exist["id"]
            patch = {k: v for k, v in payload.items() if v not in (None, "")}
            patch.pop("source", None)
            db.update_part(pid, patch)
            is_new = False
        else:
            pid = db.add_part(payload, location=location, quantity=0)
            is_new = True
        if qty:
            db.change_stock(pid, location, qty)
            db.add_txn(pid, config.TXN_IN, qty, location, operator,
                       f"{note}（{'新建' if is_new else '追加'}）")
    return pid, is_new


def update_part(part_id, data):
    """编辑元件资料。若把 C 号改成新的，不自动联网。"""
    if not db.get_part(part_id):
        raise ServiceError("元件不存在")
    db.update_part(part_id, data)
    return True


def delete_part(part_id):
    if not db.get_part(part_id):
        raise ServiceError("元件不存在")
    db.delete_part(part_id)


def refresh_from_lcsc(part_id, operator=""):
    """重新从商城拉取该元件的最新资料（库存预警、价格等）。"""
    part = db.get_part(part_id)
    if not part:
        raise ServiceError("元件不存在")
    code = (part.get("code") or "").strip()
    if not lcsc.is_lcsc_code(code):
        raise ServiceError("该元件没有嘉立创 C 号，无法刷新")
    data = lcsc.fetch_part(code, force=True)
    patch = {k: v for k, v in data.items() if not k.startswith("_") and v not in (None, "")}
    patch["last_fetch"] = config.now_str()
    patch.pop("source", None)
    db.update_part(part_id, patch)
    return data


# ---------------------------------------------------------------- 出入库
def stock_in(part_id, quantity, location=None, operator="", note=""):
    quantity = int(quantity)
    if quantity <= 0:
        raise ServiceError("入库数量必须大于 0")
    location = (location or config.DEFAULT_LOCATION).strip() or config.DEFAULT_LOCATION
    if not db.get_part(part_id):
        raise ServiceError("元件不存在")
    with db.transaction():
        total = db.change_stock(part_id, location, quantity)
        db.add_txn(part_id, config.TXN_IN, quantity, location, operator, note)
    return total


def stock_out(part_id, quantity, location=None, operator="", note="",
              allow_negative=None):
    """出库。

    allow_negative 为 None 时读设置项「允许负库存」。允许负库存时不会夹到 0，
    而是真的记成负数并在备注里写明欠账数量，保证库存和流水始终对得上。
    """
    quantity = int(quantity)
    if quantity <= 0:
        raise ServiceError("出库数量必须大于 0")
    location = (location or config.DEFAULT_LOCATION).strip() or config.DEFAULT_LOCATION
    if not db.get_part(part_id):
        raise ServiceError("元件不存在")
    if allow_negative is None:
        allow_negative = bool(config.get_setting("allow_negative_out", False))

    with db.transaction():
        cur = db.get_stock_qty(part_id, location)
        new_qty = cur - quantity
        if new_qty < 0 and not allow_negative:
            raise ServiceError(
                f"库位「{location}」当前只有 {cur} 个，不足以出库 {quantity} 个")
        db.set_stock(part_id, location, new_qty)
        if new_qty < 0:
            note = (note + f"（欠账 {abs(new_qty)} 个，待补入库）").strip()
        db.add_txn(part_id, config.TXN_OUT, quantity, location, operator, note)
    return new_qty


def adjust_stock(part_id, location, new_quantity, operator="", note="盘点调整"):
    """盘点：把某库位数量直接改为指定值，并记录差额流水。"""
    new_quantity = int(new_quantity)
    if new_quantity < 0:
        raise ServiceError("库存数量不能为负数")
    location = (location or config.DEFAULT_LOCATION).strip() or config.DEFAULT_LOCATION
    if not db.get_part(part_id):
        raise ServiceError("元件不存在")
    with db.transaction():
        cur = db.get_stock_qty(part_id, location)
        diff = new_quantity - cur
        db.set_stock(part_id, location, new_quantity)
        db.add_txn(part_id, config.TXN_ADJUST, diff, location, operator,
                   f"{note}（{cur}→{new_quantity}）")
    return new_quantity


def transfer(part_id, from_loc, to_loc, quantity, operator=""):
    quantity = int(quantity)
    if quantity <= 0:
        raise ServiceError("调拨数量必须大于 0")
    if from_loc == to_loc:
        raise ServiceError("源库位与目标库位相同")
    with db.transaction():
        cur = db.get_stock_qty(part_id, from_loc)
        if cur < quantity:
            raise ServiceError(f"库位「{from_loc}」只有 {cur} 个，不足以调拨")
        db.move_stock(part_id, from_loc, to_loc, quantity)
        db.add_txn(part_id, config.TXN_OUT, quantity, from_loc, operator,
                   f"调拨至 {to_loc}")
        db.add_txn(part_id, config.TXN_IN, quantity, to_loc, operator,
                   f"由 {from_loc} 调入")
    return db.get_total_qty(part_id)


def all_locations():
    rows = db.query("SELECT DISTINCT location FROM stock ORDER BY location")
    locs = [r["location"] for r in rows if r["location"]]
    if config.DEFAULT_LOCATION not in locs:
        locs.insert(0, config.DEFAULT_LOCATION)
    return locs


# ---------------------------------------------------------------- 备份
def backup_db():
    """把数据库备份一份到 data/backup，返回备份文件路径。"""
    src = config.DB_PATH
    if not os.path.exists(src):
        raise ServiceError("数据库尚未创建")
    stamp = config.now_str().replace("-", "").replace(":", "").replace(" ", "_")
    dst = os.path.join(config.BACKUP_DIR, f"inventory_{stamp}.db")
    return db.backup_to(dst)
