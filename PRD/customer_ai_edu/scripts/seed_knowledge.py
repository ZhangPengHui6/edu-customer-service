"""写入 10 篇 Phase 0 知识库文章与切片元数据。

用法：
    python scripts/seed_knowledge.py

向量不在这里生成（需要加载 bge-m3），切片写入后 vector_status='pending'，
由 scripts/reindex_knowledge.py 统一编码并写入 Milvus。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import func, insert, select

from edu_ai.db import SessionFactory, engine
from edu_ai.models import KnowledgeArticle, KnowledgeChunk

# 与客服库 seed 保持同一命名空间，保证 tenant_id 一致。
NS = uuid5(NAMESPACE_URL, "https://edu-cs.local/seed")
TENANT_HQ = uuid5(NS, "tenant:hq")
TENANT_NORTH = uuid5(NS, "tenant:dlr_north")
ADMIN_HQ = uuid5(NS, "user:admin_001")


def pk(name: str) -> UUID:
    return uuid5(NS, name)


def chunk_text(content: str, limit: int = 400) -> list[str]:
    """按空行聚合，单段超长时硬切。"""
    parts: list[str] = []
    buffer = ""
    for block in content.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if len(block) > limit:
            if buffer:
                parts.append(buffer)
                buffer = ""
            parts.extend(block[i : i + limit] for i in range(0, len(block), limit))
            continue
        if len(buffer) + len(block) + 2 > limit and buffer:
            parts.append(buffer)
            buffer = block
        else:
            buffer = f"{buffer}\n\n{block}" if buffer else block
    if buffer:
        parts.append(buffer)
    return parts


ARTICLES: list[dict] = [
    {
        "slug": "warranty-policy-overview",
        "scope": "all_dealers",
        "title": "学习机保修政策总览",
        "category": "warranty",
        "doc_type": "policy",
        "product_models": ["X5", "X6", "S3"],
        "content_md": (
            "整机保修期为自激活之日起 12 个月，主要部件保修 24 个月。\n\n"
            "保修范围包括非人为的硬件故障，例如无法开机、屏幕异常、触控失灵、电池异常衰减。\n\n"
            "不在保修范围的情形：进液、摔碰、私自拆机、非授权维修点改装。\n\n"
            "保修状态以设备 SN 查询结果为准，客服回答时必须引用系统查询结果，不得口头承诺。\n\n"
            "延保服务与经销商销售政策相关，经销商租户可叠加本地延保，但不得缩短总部标准保修。"
        ),
    },
    {
        "slug": "repair-process",
        "scope": "all_dealers",
        "title": "报修与维修工单流程",
        "category": "repair",
        "doc_type": "manual",
        "product_models": ["X5", "X6", "S3"],
        "content_md": (
            "报修前先完成三步自检：确认电量充足、长按电源键 15 秒强制重启、检查系统是否为最新版本。\n\n"
            "自检无效后，客服可代为创建维修工单，需收集：设备 SN、故障现象、发生时间、是否进液或摔碰、联系人。\n\n"
            "维修方式分为到店、寄修、上门三种。到店需选择服务网点；寄修由客服提供寄件地址；上门仅限部分城市。\n\n"
            "工单状态依次为：已创建、已收件、检测中、已报价、维修中、已完成、已取消。\n\n"
            "保修内维修不收取费用；保外维修需先报价，用户确认后才进入维修。"
        ),
    },
    {
        "slug": "screen-flicker",
        "scope": "tenant",
        "title": "屏幕闪烁排查指引",
        "category": "hardware",
        "doc_type": "troubleshooting",
        "product_models": ["X5", "X6"],
        "content_md": (
            "现象：屏幕亮度忽明忽暗或出现横向条纹。\n\n"
            "第一步，关闭自动亮度，观察是否仍闪烁。\n\n"
            "第二步，进入设置检查系统版本，升级到最新固件后重启。\n\n"
            "第三步，排除第三方护眼应用影响，安全模式下观察 10 分钟。\n\n"
            "以上无效时，判断为硬件问题，按保修状态引导到店检测；保修内免费更换屏幕组件。"
        ),
    },
    {
        "slug": "no-power",
        "scope": "tenant",
        "title": "设备无法开机排查指引",
        "category": "hardware",
        "doc_type": "troubleshooting",
        "product_models": ["X5", "X6", "S3"],
        "content_md": (
            "先使用原装充电器充电 30 分钟，观察充电指示灯。\n\n"
            "指示灯不亮：更换充电线与充电头，排除配件问题。\n\n"
            "指示灯亮但无法开机：长按电源键 15 秒强制重启。\n\n"
            "仍无法开机：连接电脑查看是否识别为存储设备，能识别说明屏幕或排线异常。\n\n"
            "进液或摔碰导致的不开机不在保修范围，需先报价再维修。"
        ),
    },
    {
        "slug": "battery-drain",
        "scope": "tenant",
        "title": "电池续航异常排查指引",
        "category": "hardware",
        "doc_type": "troubleshooting",
        "product_models": ["X5", "S3"],
        "content_md": (
            "先查看设置中的电池使用详情，确认是否存在异常耗电应用。\n\n"
            "建议关闭后台常驻应用，降低屏幕亮度，关闭不必要的定位与蓝牙。\n\n"
            "在 20% 电量时记录待机时长，若连续两次低于 4 小时，可判定为电池异常。\n\n"
            "保修期内电池健康度低于 80% 可免费更换；保外更换按标准报价执行。"
        ),
    },
    {
        "slug": "touch-failure",
        "scope": "tenant",
        "title": "触控失灵排查指引",
        "category": "hardware",
        "doc_type": "troubleshooting",
        "product_models": ["X6", "S3"],
        "content_md": (
            "先清洁屏幕并擦干双手，排除水渍与油污影响。\n\n"
            "取下第三方贴膜与保护壳，重新测试触控。\n\n"
            "进入工程模式执行触控校准，观察失灵区域是否固定。\n\n"
            "固定区域失灵通常为触控模组故障，需到店检测；整屏无响应先尝试强制重启。"
        ),
    },
    {
        "slug": "logistics-delay",
        "scope": "all_dealers",
        "title": "物流停滞处理口径",
        "category": "logistics",
        "doc_type": "script",
        "product_models": [],
        "content_md": (
            "当物流超过 24 小时无更新时，先查询承运方最新节点并向用户说明。\n\n"
            "标准口径：已为您联系承运方核查，预计 24 小时内更新物流，请留意短信通知。\n\n"
            "超过 48 小时仍无更新，且用户明确表示着急使用，可转人工由售后专员跟进。\n\n"
            "不得承诺具体送达时间，不得承诺赔偿金额；涉及赔付一律转人工处理。"
        ),
    },
    {
        "slug": "cancel-order-policy",
        "scope": "all_dealers",
        "title": "未发货订单取消规则",
        "category": "order",
        "doc_type": "policy",
        "product_models": [],
        "content_md": (
            "仅状态为待付款或已付款且未发货的订单可以取消。\n\n"
            "已发货订单不能直接取消，应引导用户拒收或申请退货。\n\n"
            "取消操作必须由用户明确确认，AI 不得自行发起。\n\n"
            "取消成功后原路退款，到账时间以支付渠道为准，通常为 1 至 3 个工作日。\n\n"
            "同一订单重复取消请求直接返回首次结果，不得重复提交。"
        ),
    },
    {
        "slug": "data-privacy",
        "scope": "all_dealers",
        "title": "家长与学生学习数据隐私说明",
        "category": "privacy",
        "doc_type": "policy",
        "product_models": ["X5", "X6", "S3"],
        "content_md": (
            "学习报告、学习时长、错题数据属于学生个人信息，仅向绑定监护人展示。\n\n"
            "客服不得向非监护人透露学生学习数据，必要时先完成身份核验。\n\n"
            "设备 SN、订单号、手机号在工单与日志中必须脱敏展示。\n\n"
            "涉及数据导出、删除的请求转人工处理，并在工单中记录。\n\n"
            "任何情况下不得索取用户密码、支付密码或短信验证码。"
        ),
    },
    {
        "slug": "complaint-handling",
        "scope": "all_dealers",
        "title": "投诉安抚与升级流程",
        "category": "complaint",
        "doc_type": "script",
        "product_models": [],
        "content_md": (
            "识别信号：用户提到投诉、曝光、12315、退款不处理、反复维修未解决。\n\n"
            "第一步先共情并复述问题，不辩解、不打断。\n\n"
            "第二步给出可执行的下一步与时间点，例如今天内由售后专员回电。\n\n"
            "第三步立即创建转人工工单，优先级 P1；涉及媒体或监管的升级为 P0。\n\n"
            "不得承诺赔偿金额，不得评价其他部门或经销商。\n\n"
            "转人工后 AI 停止自动回复，由人工接管会话。"
        ),
    },
]


async def seed() -> None:
    async with SessionFactory() as session:
        existing = await session.scalar(select(func.count()).select_from(KnowledgeArticle))
        if existing:
            print(f"已存在 {existing} 篇知识文章，跳过 seed。")
            return

        article_rows: list[dict] = []
        chunk_rows: list[dict] = []

        for item in ARTICLES:
            article_id = pk(f"knowledge:{item['slug']}")
            tenant_id = TENANT_HQ if item["scope"] == "all_dealers" else TENANT_NORTH
            article_rows.append(
                {
                    "id": article_id,
                    "tenant_id": tenant_id,
                    "slug": item["slug"],
                    "scope": item["scope"],
                    "title": item["title"],
                    "category": item["category"],
                    "doc_type": item["doc_type"],
                    "product_models": item["product_models"],
                    "content_md": item["content_md"],
                    "status": "published",
                    "version": 1,
                    "effective_from": None,
                    "effective_to": None,
                    "source": "phase0-seed",
                    "created_by": ADMIN_HQ,
                }
            )
            for index, text in enumerate(chunk_text(item["content_md"])):
                chunk_rows.append(
                    {
                        "id": pk(f"chunk:{item['slug']}:{index}"),
                        "tenant_id": tenant_id,
                        "article_id": article_id,
                        "chunk_index": index,
                        "text": text,
                        "token_count": None,
                        "vector_status": "pending",
                        "indexed_at": None,
                    }
                )

        await session.execute(insert(KnowledgeArticle), article_rows)
        await session.execute(insert(KnowledgeChunk), chunk_rows)
        await session.commit()

    print(f"知识库 seed 完成：{len(article_rows)} 篇文章 / {len(chunk_rows)} 个切片。")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
