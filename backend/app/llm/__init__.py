"""模型层：统一封装「对话生成」和「向量化」两类能力。

对外只暴露：
- router.router.chat(task, messages)  —— 按任务档位路由到合适的模型，自动降级
- embeddings.embed_texts(texts)       —— 向量化（本地 bge-m3 → 字符 n-gram 保底）

业务代码不关心、也看不到自己调的是云端还是本地模型。
"""
