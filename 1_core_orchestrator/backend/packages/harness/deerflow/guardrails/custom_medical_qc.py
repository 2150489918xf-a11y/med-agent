from typing import Any, Dict

from deerflow.guardrails.provider import GuardrailProvider, GuardrailResult

class MedicalQualityControlProvider(GuardrailProvider):
    """
    医疗专用的质控拦截器 (替代原有的 a5_quality.py)。
    可以在大模型输出给用户或者执行敏感工具之前，进行一层“硬拦截”。
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.strict_mode = config.get("strict_mode", True)
        # 这里可以加载 p0_p4 医疗违规词汇表、诊断确信度判定正则等
        self.prohibited_words = ["确诊", "处方", "我断定", "一定是"]

    async def aevaluate(
        self,
        messages: list[Any],
        tools: list[Any],
        sandbox_state: Dict[str, Any] | None,
        tool_call: dict | None = None,
        message_to_send: str | None = None,
    ) -> GuardrailResult:
        # 我们只在即将输出文本给给患者时做拦截 (message_to_send 不为空)
        # 或者遇到极其危险的操作工具时拦截
        
        if message_to_send:
            # 1. 检测是否有确切诊断的越权词汇
            for word in self.prohibited_words:
                if word in message_to_send:
                    return GuardrailResult(
                        allowed=False,
                        reason=f"【触发 A5 医疗安全阻断】禁止使用确切的诊断词汇'{word}'。",
                        directive=f"请修改你的输出，强调本建议仅供临床医师参考，不可使用'{word}'。"
                    )
            
            # 2. 检查输出中是否明显遗漏了“仅供参考”的免责声明
            if "仅供参考" not in message_to_send and self.strict_mode:
                return GuardrailResult(
                    allowed=False,
                    reason="【触发 A5 医疗安全阻断】未检测到免责声明。",
                    directive="请在建议的结尾补上：'本意见仅供参考，最终诊断需要临床医师结合体征确认'。"
                )
        
        # 如果是工具调用拦截（例如，试图去后台库随意发药）
        if tool_call and tool_call.get("name") == "issue_prescription":
            return GuardrailResult(
                allowed=False,
                reason="【越权操作拦截】A2 / A3 Agent 没有开具处方的权限！",
                directive="请取消开药的请求，转而只给出用药建议。"
            )
            
        return GuardrailResult(allowed=True)
