# Phase 7: Subagent Fast Routing Optimization

- [ ] 编写 `FastRouteMiddleware` 以直接拦截带图像的请求并模拟 Tool Call
- [ ] 在 `agent.py` 的中介件链路中注册 `FastRouteMiddleware`
- [ ] 测试影像分析任务的触发时延 (目标：从 90s 下降至 2s 内)
