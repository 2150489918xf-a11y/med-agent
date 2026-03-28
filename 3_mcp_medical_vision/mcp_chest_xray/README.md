# MCP Vision Service — 医学影像 AI 分析

> 基于 Pipeline V3 的 MCP 服务，提供胸片 AI 分析能力。

## 目录结构

```
mcp_vision/
├── server.py           # MCP 入口，暴露 tools
├── engine.py           # V3 Pipeline 核心引擎
├── config.py           # 路径 & 设备配置
├── requirements.txt    # Python 依赖
├── models/             # 模型权重 (symlink)
│   ├── yolov8_vinbigdata_acc867.pt
│   └── medsam_vit_b.pth
└── README.md
```

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 MCP Server (stdio 模式)
python server.py
```

## MCP 客户端配置

```json
{
  "mcpServers": {
    "vision": {
      "command": "python",
      "args": ["e:/path/to/mcp_vision/server.py"]
    }
  }
}
```
