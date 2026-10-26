## 初始化项目需求

【核心目标】
   用于初始化项目架构
【已知背景】
   目前已知项目掌柜智库 代码地址：
   C:\data\python_data\customer-service
   C:\data\python_data\ai-service
【具体要求】
   1   先阅读参考代码 结合学习机公司做智能客服 给出修改建议 
   2   先不要直接生成代码 给我具体方案 让我逐项确定要修改内容
   3   生成项目PRD文档 文档地址 
   yxp_edu_file/PRD/customer_service_edu_PRD.md
   yxp_edu_file/PRD/customer_ai_edu_PRD.md
   4   项目存放路径
   yxp_edu_file/PRD/customer_service_edu
   yxp_edu_file/PRD/customer_ai_edu

A-01 B
A-02 B
A-03 B
A-04 A
A-05 A
A-06 A
A-07 A
A-08 A
A-09 A
A-10 A pg+milvus

B 部分全同意

注意： 在 yxp_edu_file/config.md中存放我给你的 以及你自己总结的相关配置信息 之后使用大模型使用七牛云 DASHSCOPE_API_KEY=sk-3e1e631ef902f637ccb9f1400136ddd847a00d635405f6b17183161b01cb4193
DASHSCOPE_BASE_URL=https://api.qnaigc.com/v1

使用的后端环境在192.168.168.100 你自己查询使用相关技术栈 用到的连接信息保存到 yxp_edu_file/config.md

先不着急写代码 先确认以上



1 租户设置经销商和总部
2 没有真实数据 你自己在数据库中建表 生成测试数据
3 新建对应数据库 自己建表造测试数据
4 部署在192.168.168.100 已经安装
5 使用bge-m3
把两份 PRD 的决策表、MVP 范围、技能清单同步为“已确认版本”（A-01 B 会删减技能，A-03 B 会给所有表加租户，A-10 会把 RAG 从 pgvector 改为 Milvus）。
给出最终的目录结构、数据库/Collection 命名、接口契约清单，再开始搭骨架。



【核心目标】
   设计对应的前端代码原型
【已知背景】
   目前已知项目掌柜智库 代码地址：
   3生成项目PRD文档 文档地址 
   yxp_edu_file/PRD/customer_service_edu_PRD.md
   yxp_edu_file/PRD/customer_ai_edu_PRD.md
   项目存放路径
   yxp_edu_file/PRD/customer_service_edu
   yxp_edu_file/PRD/customer_ai_edu
【具体要求】
   1   开发服务对应的原型 使用pen.dev
   2   功能尽可能的简单 不要太过于复杂
   3    不要开发实现不了的功能 能够在后端代码中找到对应的数据忌口