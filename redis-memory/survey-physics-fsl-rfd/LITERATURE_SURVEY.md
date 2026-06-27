# 文献调研：物理感知少样本学习的旋转机械故障诊断方法综述

**项目ID**: fb99aa24-01f
**日期**: 2026-06-27
**阶段**: Phase 1 — 文献调研

---

## 1. 调研范围与方法

### 1.1 调研主题
物理感知（Physics-Aware）与少样本学习（Few-Shot Learning）相结合的旋转机械故障诊断方法综述。

### 1.2 检索数据库
- Web Search (arXiv, Google Scholar, ScienceDirect)
- Semantic Scholar API
- CNKI (中国知网)

### 1.3 检索关键词
- `physics-informed neural network` + `fault diagnosis` + `rotating machinery`
- `physics-guided` + `deep learning` + `bearing fault diagnosis`
- `few-shot learning` + `fault diagnosis` + `rotating machinery`
- `meta-learning` + `prototypical network` + `fault diagnosis`
- `物理感知` + `少样本学习` + `旋转机械` + `故障诊断`
- `physics-aware few-shot learning`

---

## 2. 领域背景与研究动机

旋转机械故障诊断的核心挑战在于：
1. **故障样本稀缺**：实际工业场景中，故障数据获取成本高、标注困难
2. **工况复杂多变**：转速、负载等运行条件变化导致数据分布漂移
3. **物理机理与数据驱动的鸿沟**：纯数据驱动方法缺乏物理可解释性和鲁棒性

少样本学习（FSL）解决第1点，物理感知（Physics-Aware）方法解决第3点，二者结合有望同时解决上述三大挑战。本综述旨在系统梳理这两个维度的交叉研究现状。

---

## 3. 少样本故障诊断方法分类

### 3.1 元学习方法 (Meta-Learning)

| 方法 | 核心思想 | 代表文献 |
|------|---------|---------|
| MAML | 学习模型初始化参数，快速适应新任务 | Finn et al. (2017) |
| ProtoNet | 学习嵌入空间中类别原型，基于距离度量分类 | Snell et al. (2017) |
| RelationNet | 学习可学习的距离度量函数 | Sung et al. (2018) |
| 弹性原型网络 | 引入弹性因子增强特征空间区分性 | 2024, RSS |

**代表性工作：**

- **Jiang et al. (2023, JIM)**: 双分支原型网络(TBPN)，融合时域和频域特征，在工业互联网企业数据集上验证了少样本诊断有效性
- **Wang & Liu (2025, JIM)**: 多尺度元学习网络(MS-MLN)，结合episodic metric学习策略，在轴承和风电齿轮箱上优于基准模型
- **弹性原型网络 (2024, RSS)**: 针对不稳定转速下的少样本跨域诊断，引入弹性因子增强泛化能力

### 3.2 迁移学习方法 (Transfer Learning)

| 类别 | 方法 | 特点 |
|------|------|------|
| 实例迁移 | 样本重加权 | 利用源域样本分布信息 |
| 模型迁移 | 预训练-微调 | 在大规模数据上预训练后迁移 |
| 特征迁移 | 领域自适应(DA) | 对齐源域和目标域特征分布 |
| 领域泛化(DG) | 不依赖目标域数据 | 学习域不变特征 |

**代表性工作：**

- **Xiao et al. (2025, AEI)**: 综述领域泛化在旋转机械故障诊断中的应用，发布了统一算法框架
- **毛凯宁 (2023, 四川大学硕士论文)**: 提出DKCAN、SAASN、MPRFN三种领域自适应方法
- **哈尔滨工业大学综述 (2025)**: 系统梳理预训练-微调、特征迁移、领域自适应在故障诊断中的应用

### 3.3 数据增强方法

- **GAN-based**: 利用生成对抗网络扩充故障样本 (Zou, 2025)
- **频域变换增强**: STFT、小波变换等生成时频图
- **物理约束增强**: 基于物理模型生成合成样本

### 3.4 自监督学习方法

- **TFPred (2024)**: 时频预测自监督框架，从无标签数据中学习判别性表示
- **对比学习**: MoCo、SimCLR等应用于振动信号特征学习
- **物理引导自监督学习 (PgSSL, 2026)**: 利用平均能量密度、熵等物理量作为监督信号

### 3.5 现有综述论文

| 文献 | 年份 | 范围 | 主要贡献 |
|------|------|------|---------|
| 吴轲等 (2025, 中国舰船研究) | 2025 | 深度学习小样本故障诊断 | 分元学习/迁移/泛化/增强/自监督5类综述 |
| Wang et al. (2024, MST) | 2024 | 机器学习故障诊断综述 | 覆盖ELM/SVM/CNN/DBN/GAN/GNN |
| Sustainability (2023) | 2023 | FSL在机械故障诊断 | 2018-2023年FSL方法系统回顾 |

---

## 4. 物理感知故障诊断方法分类

### 4.1 物理信息神经网络 (PINNs)

| 文献 | 年份 | 方法 | 应用 |
|------|------|------|------|
| Shen et al. | 2021 | 阈值模型+CNN物理融合 | 轴承故障检测 |
| Sensors (2024) | 2024 | PINN参数估计 | Jeffcott转子健康监测 |
| Souza et al. (PHM 2025) | 2025 | PIDL轴承故障分类 | 六种工况分类 |
| PIPDN (AEI, 2024) | 2024 | 物理信息概率深度网络 | 可解释机械故障诊断 |

### 4.2 物理引导网络架构

- **小波卷积 (LWCNet, 2026)**: 将拉普拉斯小波先验嵌入卷积结构，增强可解释性
- **PI-MBDNet (2025)**: 经验小波变换+自适应频段划分+多分支架构，适用于大型多列圆锥轴承
- **自适应小波滤波器CNN (PHM, 2025)**: 基于信号处理方法设计物理层，自适应提取故障特征

### 4.3 物理约束与先验知识嵌入

| 方法 | 物理先验形式 | 嵌入方式 |
|------|------------|---------|
| 平均能量密度方程 | 能量守恒定律 | 作为SSL监督信号 |
| 包络谱峭度 | 故障冲击特征 | 特征选择准则 |
| 希尔伯特变换 | 调制解调原理 | 时频分析层 |
| 动力学方程 | 转子-轴承动力学 | 损失函数约束 |

### 4.4 物理引导的多模态融合

- **LWCNet (2026)**: 2D时频图编码器 + 1D振动信号编码器
- **物理引导多模态少样本框架**: 拉普拉斯小波卷积 + 马氏距离原型度量
- **声-振物理信息融合**: 2025年提出的声振物理信息约束引导方法

---

## 5. 物理感知与少样本学习的交叉领域

这是本综述的核心创新方向。目前该交叉领域处于早期阶段，代表性工作包括：

### 5.1 LWCNet (Hu et al., 2026, CMC)

**核心贡献**：首次系统性地将物理先验嵌入少样本故障诊断框架
- **物理层**: 拉普拉斯小波卷积(LWC)模块，多分辨率分析先验
- **少样本策略**: 马氏距离原型联合度量
- **多模态**: 时频图 + 振动信号双编码器
- **数据集**: CWRU、PU轴承数据集

### 5.2 物理引导双流融合 (2026, Processes)

针对极端少样本和剧烈域漂移场景：
- 拉普拉斯小波 + STFT预处理
- 双流架构处理域漂移
- 自适应批归一化(AdaBN)
- 长尾分布支持集设计

### 5.3 物理引导自监督少样本学习 (PgSSL, 2026)

- 物理量(能量密度、熵、峭度等)作为自监督信号
- 非线性投影结构(物理头)
- 在小样本条件下保持物理一致性

### 5.4 待突破的关键问题

| 问题 | 现状 | 挑战 |
|------|------|------|
| 物理先验与可学习表示的平衡 | 固定小波 vs 可学习小波 | 过度约束降低灵活性 |
| 跨工况泛化中的物理一致性 | 部分领域自适应 | 物理定律是否跨域保持不变？ |
| 物理可解释性的量化评估 | 缺乏统一指标 | 如何衡量"物理一致性"？ |
| 多源物理先验融合 | 单一先验为主 | 多种物理量如何协同？ |

---

## 6. 公开数据集与基准

| 数据集 | 故障类型 | 采样率 | 工况 | 来源 |
|--------|---------|--------|------|------|
| CWRU | 轴承单点故障 | 12k/48k Hz | 4种负载 | 凯斯西储大学 |
| PU | 轴承多种故障 | 64k Hz | 多种工况 | Paderborn大学 |
| HUST | 轴承故障 | - | 变转速 | 华中科技大学 |
| XJTU-SY | 轴承全寿命 | 25.6k Hz | 3种工况 | 西安交大 |
| MFPT | 轴承故障 | 97.7k Hz | 多种 | 美国故障预防技术学会 |

---

## 7. 研究趋势与前沿方向

### 7.1 方法演进趋势
```
纯数据驱动 (2018-2020)
  → 少样本学习 (2020-2023)
    → 物理感知深度学习 (2021-2024)
      → 物理感知+少样本学习 (2024-至今)  ★ 前沿交叉
```

### 7.2 未来方向

1. **物理知识图谱引导的少样本学习**: 构建故障机理知识图谱，辅助少样本特征学习
2. **大模型+物理先验**: 预训练大模型(如Transformer)注入物理约束
3. **跨设备物理迁移**: 研究不同机械系统中共享的物理规律，实现跨设备知识迁移
4. **物理一致性生成**: 生成对抗网络中加入物理约束，生成物理有效的故障样本
5. **不确定性量化**: 结合物理先验进行贝叶斯推断，量化诊断不确定性
6. **联邦学习+物理感知**: 保护数据隐私的同时利用物理先验

---

## 8. 文献列表

### 综述论文

1. 吴轲, 吴军, 舒启明, 等. 基于深度学习的旋转机械小样本故障诊断方法研究综述[J]. 中国舰船研究, 2025, 20(2): 3-19.
2. Wang, Q., et al. A survey on fault diagnosis of rotating machinery based on machine learning[J]. Measurement Science and Technology, 2024, 35: 102001.
3. Xiao, Y., Shao, H., et al. Domain generalization for rotating machinery fault diagnosis: A survey[J]. Advanced Engineering Informatics, 2025, 64: 103063.
4. Sustainability. Few-shot learning approaches for fault diagnosis: A comprehensive review[J]. 2023, 15(20): 14975.
5. Matania, O., et al. A systematic literature review of deep learning for vibration-based fault diagnosis of critical rotating machinery: Limitations and challenges[J]. Journal of Sound and Vibration, 2024.
6. Pan, T., et al. Generative adversarial network in mechanical fault diagnosis under small sample: A systematic review[J]. ISA Transactions, 2022.
7. 哈尔滨工业大学. 迁移学习驱动机械装备智能故障诊断方法综述[J]. 2025.

### 少样本故障诊断

8. Jiang, C., Chen, H., Xu, Q., Wang, X. Few-shot fault diagnosis of rotating machinery with two-branch prototypical networks[J]. Journal of Intelligent Manufacturing, 2023, 34: 1667-1681.
9. Wang, Y., Liu, S. A multi scale meta-learning network for cross domain fault diagnosis with limited samples[J]. Journal of Intelligent Manufacturing, 2025, 36: 2841-2861.
10. Zhang, Y., et al. Domain adaptation meta-learning network with discard-supplement module for few-shot cross-domain rotating machinery fault diagnosis[J]. Knowledge-Based Systems, 2023, 268: 110484.
11. Meta-learning with elastic prototypical network for fault diagnosis under unstable speeds[J]. Reliability Engineering & System Safety, 2024.
12. Wang, D., et al. Metric-based meta-learning model for few-shot fault diagnosis under multiple limited data conditions[J]. Mechanical Systems and Signal Processing, 2021.
13. TFPred: Learning discriminative representations from unlabeled data for few-label rotating machinery fault diagnosis[J]. Mechanical Systems and Signal Processing, 2024.

### 物理感知方法

14. Shen, S., et al. A physics-informed deep learning approach for bearing fault detection[J]. Engineering Applications of Artificial Intelligence, 2021, 103: 104295.
15. Physics-Informed Neural Networks for the Condition Monitoring of Rotating Shafts[J]. Sensors, 2024, 24(1): 207.
16. Physics-informed probabilistic deep network with interpretable mechanism for trustworthy mechanical fault diagnosis[J]. Advanced Engineering Informatics, 2024.
17. Souza, L., et al. Bearings Fault Detection via Physics-Informed Convolutional Neural Networks[C]. PHM Society Conference, 2025.
18. Hassannejad, R., et al. Adaptive Wavelet-Based Physics-Informed CNN for Bearing Fault Diagnosis[J]. IJPHM, 2025, 16(1).
19. PI-MBDNet: An interpretable and physics-informed adaptive multi-branch deep learning framework[J]. Engineering Applications of Artificial Intelligence, 2025.
20. Physics-guided self-supervised learning for rotating-machinery fault diagnosis: role of average energy density equation[J]. Advanced Engineering Informatics, 2026.

### 物理感知+少样本（核心交叉领域）

21. Hu, Y., Xu, W., Du, X. LWCNet: A Physics-Guided Multimodal Few-Shot Learning Framework for Intelligent Fault Diagnosis[J]. Computers, Materials & Continua, 2026, 87(2).
22. Physics-Guided Dual-Stream Fusion for Extreme Few-Shot Fault Diagnosis Under Massive Domain Shifts[J]. Processes, 2026, 14(12): 2012.
23. Sound-vibration physical-information fusion constraint-guided deep learning method for rolling bearing fault diagnosis[J]. Reliability Engineering & System Safety, 2025.

---

## 9. 结论与建议

### 主要发现

1. **交叉领域尚处早期**: 物理感知与少样本学习的系统性结合工作（2024年至今）数量有限，存在明显研究空白
2. **物理先验多样化**: 小波变换、能量方程、统计矩、动力学方程等多种物理先验已被探索
3. **少样本框架成熟**: 元学习、迁移学习、自监督学习等方法体系已较为完善，但缺乏物理一致性的保障

### 建议研究方向

1. 构建统一的**物理感知少样本学习框架**，将物理先验嵌入元训练过程
2. 设计**物理一致性正则化**，确保少样本条件下的诊断结果符合物理规律
3. 探索**多模态物理融合**，融合振动、声学、温度等多源传感器的物理信息
4. 开发**物理驱动的小波变换层**，作为可微分的物理先验模块嵌入网络
5. 建立**物理可解释性评价指标**，量化模型的物理一致性程度
