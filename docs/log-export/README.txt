Codex 项目对话日志 — 官方工具的本地兼容修复版

TEAM_ID=contest2026_087_gaiduimingyizhanyongdui
GITHUB_LOGIN=muze20060502-beep

基于 open-vela/.claude 官方工具的版本：10743591d1034480ecee7c8ffffe9bb251d4474d
本地增加 native Codex rollout 读取与显式历史补导入口；复用官方脱敏、事件写入、清单写入及导出复制流程。
用未修改的官方 validate-log.py 及 schema 校验通过，详见 validation.txt。
本机原始 source=vscode、originator=codex_work_desktop，因此标为 vscode_extension_partial，并明确说明是 Codex Desktop 的部分内容历史恢复，不是实时完整 CLI 采集。
generator 明确包含 local-fix，不冒充已发布的官方版本。补丁和适配器放在 provenance/。

会话 ID、逐条时间戳、正文和调用 ID 来自原始记录；模型仅在源记录明确给出时填写；不生成 token 统计。
包含可见用户与助手消息及工具调用/结果。未导出系统/开发者指令、内部推理、媒体及重复运行元数据。
仅对用户明确选择的三个项目相关历史会话进行补导，不伪造 .repo 工作区，不改原始记录。
原始记录哈希、字节数和导出时刻见 manifest 中 source_integrity，可供本机复核。
未加入 DSH 历史，不可用于声称此前 DSH 对话由 Codex 完成。活跃会话是导出时的快照。

格式校验通过不等于组委会认可。本地修复尚未获上游审核，需向组委会说明来源和恢复方法。
日志可能含个人信息或工具返回的敏感数据；本次仅生成本地交付包，尚未推送 GitHub、删除旧日志或启用全局自动采集。
本包替代上一个 custom-codex-rollout-recovery 格式的本地候选包；不要把两份 manifest 混合使用。
