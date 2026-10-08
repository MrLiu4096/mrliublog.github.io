+++
title = "从 Subconverter 到 Sub-Store：Docker 与 Mihomo 多场景分流、AI 测活及校园网 DNS 实战"
date = 2026-09-05
lastmod = 2026-10-08
tags = ["Docker", "Sub-Store", "Mihomo", "Clash", "校园网", "Homelab"]
categories = ["技术折腾"]
series = ["家庭网络与边缘计算"]
summary = "记录家庭订阅服务从 Subconverter 迁移到 Sub-Store 的过程，梳理运营商与地区分组、OpenAI 端点测活、微信直连、ZeroTier 配置下发和校园网 DNS 边界，并附完整的脱敏部署与客户端配置。"
showToc = true
tocOpen = true
+++

折腾代理配置时，首先要分清三件事：订阅能否下载、节点能否连通，以及具体业务能否正常使用。

订阅服务返回正常，不代表终端加载了同一份规则；测速延迟很低，也不代表 AI 服务一定可用。切换到校园网后，还需要处理认证页面、内部域名和 DHCP 下发的 DNS。把这些环节分开，排查才有明确方向。

家里的订阅服务最初使用 Subconverter 的 `pref.ini` 和底包模板。经过迁移，目前采用 **Sub-Store 独立转换与生成配置，OpenClash 或 Mihomo 客户端执行分流**。本文介绍这套方案的部署结构、分组逻辑和排查方法，并提供可复用的配置与生成脚本。

> 文中的 NAS 地址、学校域名、订阅名称和后端路径均为示例，使用前请替换为自己的值。家庭分流与微信直连已经过实际测试；校园网配置需要结合所在网络的认证方式、DNS 和路由进行验证。

## 1. 架构：配置在 NAS 生成，流量在客户端处理

整体链路如下：

```text
上游订阅
   │  由 Sub-Store 下载；必要时使用 OpenClash 的 HTTP 代理
   ▼
NAS 上的 Sub-Store
   ├─ 转换为 ClashMeta 节点
   └─ 文件脚本：生成策略组、DNS、规则及运行参数
             │
             ├─ LAN 地址：3002 → 容器 3000
             └─ ZeroTier 地址：3002 → 容器 3000
                          │
                          ▼
             OpenClash / Mihomo 客户端
             DNS 解析、规则匹配、节点测速与实际转发
```

NAS 运行 `xream/sub-store:latest`，采用前后端合并模式，数据持久化到容器的 `/opt/app/data`。本文使用的后端版本为 `2.42.2`。

**Sub-Store 负责生成配置，客户端负责执行配置。** 客户端面板中的选择和连接记录反映实际流量走向；Sub-Store 首页能够打开，只说明网页可访问，还需要继续检查订阅下载和文件生成。

只下载“节点订阅”，只能取得节点信息。要同步策略组、DNS 和规则，应订阅文件脚本生成的完整 YAML。Sub-Store 的格式转换与脚本能力见[项目说明](https://github.com/sub-store-org/Sub-Store)。

### 1.1 从 Subconverter 迁移到 Sub-Store

早期方案依赖 Subconverter 的 `pref.ini`、`all_base.tpl` 和 25500 端口。迁移时，先停止 Subconverter，检查 Sub-Store 的节点输出和完整配置生成是否仍然正常，再删除旧容器并移除 Compose 中对应的服务。

这套订阅与文件脚本已经能够独立工作，因此不再需要维护 Subconverter 的 `api_mode`、`default_url` 或短链接。迁移自己的配置时，也应先检查脚本是否调用外部转换服务，再决定是否移除旧组件。

### 1.2 为 LAN 和 ZeroTier 分别发布端口

曾遇到 NAS 的 ZeroTier 地址可达，但远程设备无法访问 Sub-Store 3002 端口的情况。原因是 Docker 只把端口发布到了 NAS 的 LAN 地址。

为 ZeroTier 地址补上端口发布后，两个入口都能直接访问服务：

```yaml
ports:
  - "192.168.10.20:3002:3000"
  - "192.168.200.20:3002:3000"
```

这里的两个地址分别代表 NAS 的 LAN 和 ZeroTier 地址。排查远程访问时，应依次检查虚拟网络连接、目标路由、服务端口发布和 HTTP 响应。

地址绑定决定服务在哪个目标地址上接受连接，不等同于限制来源网络。如果其他网络存在到该地址的路由，仍可能访问它；来源限制需要由防火墙等访问控制实现。

终端应使用前端复制出的**生成文件链接**。切换到 ZeroTier 入口时，更换主机地址并保留生成路径和参数，不能用前端首页代替订阅链接。

## 2. 先检查订阅下载，再排查配置生成

曾经出现“网页正常，下载节点和生成文件却返回 500”的故障。检查发现，上游订阅仍有响应，但容器下载时发生连接超时；通过家里 OpenClash 的 HTTP 代理下载则成功。

解决方法是在目标订阅的下载代理字段中设置现有 HTTP 代理。例如：

```text
http://192.168.10.2:7893
```

这个地址用于 Sub-Store **下载上游订阅**，与生成配置中的 `出口选择` 分属不同环节。前者影响 NAS 如何取得订阅，后者影响客户端如何转发业务流量。

使用下载代理后，订阅更新会依赖该代理的可用性。如果新的拉取失败，应先检查代理和上游连通性。客户端已经保存的配置能否继续使用，则取决于配置是否有效及节点是否可用。

排查可以按以下顺序进行：

1. 确认 Sub-Store 首页可访问。
2. 确认目标订阅能重新下载。
3. 确认生成文件返回有效 YAML。
4. 确认客户端成功更新并加载完整配置。
5. 查看实际连接命中的规则和出口。

## 3. 策略组保持单向依赖，运营商与 AI 分组平级

策略组互相引用，会导致内核报告 `loop is detected in ProxyGroup`。为避免循环，配置采用单向依赖：

```text
出口选择（手动选择器）
  ├─ 移动优选 / 联通优选 / 电信优选 → 真实节点
  ├─ 地区-运营商测速组               → 真实节点
  ├─ AI 测速组                      → 真实节点
  ├─ 手动选择                       → 真实节点
  └─ DIRECT
```

底层测速组只包含真实节点，不反向引用顶层选择器。“手动选择”同样只列出节点。

当订阅包含所有对应地区和运营商节点时，可以生成 19 个策略组：

| 类型 | 策略组 |
| --- | --- |
| 总出口 | 出口选择 |
| 运营商优选 | 移动优选、联通优选、电信优选 |
| 地区与运营商 | 香港、台湾、日本、新加坡、美国，分别有移动和联通组 |
| AI 测活 | AI-香港-移动、AI-新加坡-移动、AI-美国-移动、AI-移动优选 |
| 手动节点池 | 手动选择 |

“移动优化”“联通优化”等分类来自上游节点名称，脚本据此筛选。名称本身不能证明线路质量，仍要结合实际延迟和使用体验选择。

**先在“出口选择”中选择合适的组，URL-test 再在该组成员中择优。** 例如，家庭移动宽带可以先尝试“移动优选”，需要固定地区时选择对应地区组。这套配置不会自动识别当前网络的运营商。

### 3.1 校验节点名，跳过空分组

生成配置前，脚本检查空节点名、重复节点名，以及与策略组或内置名称冲突的节点名，避免上游重命名后出现有歧义的引用。

没有匹配节点的测速组会被跳过，其入口也不会加入总选择器。因此，订阅缺少某些地区节点时，最终组数可能少于 19 个。

地区和运营商筛选在 Sub-Store 的 JavaScript 中完成。不同组件的正则语法存在差异，例如 Go 标准正则的[语法列表](https://pkg.go.dev/regexp/syntax)不包含前向断言。附录脚本使用地区匹配与运营商匹配两个条件取交集，便于维护。

### 3.2 修改组名时，同步检查引用

AI 测速组直接列入“出口选择”，与普通地区组平级。OpenAI 相关规则、规则集下载代理和 DNS URL 中的组名引用统一指向“出口选择”。

增加、删除或重命名策略组时，需要一起检查：

- `proxy-groups[].proxies` 中的成员引用。
- `rules` 中的策略目标。
- `rule-providers[].proxy` 中的下载出口。
- DNS URL 中的 `#组名`。

这些名称必须保持一致，否则可能出现组不存在或引用失效的问题。

## 4. AI 测活：端点连通与业务可用分开验证

普通测速组使用返回 204 的端点：

```yaml
url: https://www.gstatic.com/generate_204
expected-status: 204
```

四个 AI 组使用 OpenAI API 端点：

```yaml
url: https://api.openai.com/v1/models
expected-status: 401
```

请求不携带 API 凭据，以预期的 401 响应作为端点连通探测。它检查了 HTTP 响应，但不代表 ChatGPT 对话、API 账户业务或 Gemini 一定可用；实际服务仍需使用自己的账号和客户端测试。

AI 组包含香港移动节点，“AI-移动优选”覆盖所有匹配移动名称的地区。这些组使用同一个 OpenAI 测试地址，不是 Gemini 专用测速组。需要使用 Gemini 时，应单独验证所选出口的实际可用性。

测速参数如下：

| 参数 | 设置 |
| --- | --- |
| 检查间隔 | 300 秒 |
| 单次超时 | 5000 毫秒 |
| 切换容差 | 80 毫秒 |
| 最大失败次数 | 3 |
| 普通组 lazy | true |
| AI 组 lazy | false |

普通组在未选中时减少定期测试；AI 组保留后台定期检查。`max-failed-times` 超过阈值后触发强制健康检查，实际切换还取决于检查结果和组内可用节点。字段语义见[Mihomo 代理组文档](https://wiki.metacubex.one/config/proxy-groups/)。

AI 流量统一跟随“出口选择”：选择普通组时，AI 流量也使用该组；选择 AI 组时，公共代理出口采用对应的 OpenAI 端点测速结果。这一点需要与“为 AI 业务单独设置出口”的方案区分开。

## 5. DNS 分开处理启动解析、节点解析和业务查询

配置按用途划分 DNS：

| 用途 | 设置 |
| --- | --- |
| DNS 服务器域名的初始解析 | default-nameserver 使用 119.29.29.29 |
| 代理节点域名解析 | 阿里与腾讯 DoH |
| 默认业务域名查询 | Google 与 Cloudflare DoH，指定“出口选择” |
| 国内、私有域名分类 | 按 geosite 策略交给国内 DoH |
| 微信相关域名 | 国内 DoH，并加入 Fake-IP 排除项 |

把节点域名解析与代理业务查询分开，可以避免节点尚未解析出来，就先要求通过该节点查询 DNS。各字段的职责见[Mihomo DNS 配置](https://wiki.metacubex.one/config/dns/)。

> 2026 年 10 月 7 日，订阅方通知 `223.5.5.5` 存在节点域名解析污染问题。基于这一反馈，配置移除了 `default-nameserver` 中的该地址，保留 `119.29.29.29`。这是针对订阅方反馈采取的配置调整，不能仅凭通知判断其他订阅源也存在相同问题。

阿里 DoH 仍然保留。访问 DoH 服务与把某个 IP 设置为明文 DNS 上游，是不同的配置方式。

### 5.1 海外手机号微信用户：为相关域名与 CDN 设置直连

**本节面向绑定海外手机号，或遇到类似微信图片加载缓慢问题的用户。** 调整参考了 Deep Router 的[《解决微信图片加载缓慢：从 DNS 到 OSPF 路由的问题排查》](https://deeprouter.org/article/debug-wechat-image-slow-ospf-routing)，并结合家里的 OpenClash / Mihomo 配置实施。实际使用测试确认，这项调整有效，改善了微信图片加载缓慢的问题。

参考文章记录了微信绑定英国手机号后，访问腾讯海外 CDN 时受到分流路由影响的案例。原作者通过调整 BIRD / OSPF 路由恢复图片加载；家里的方案则借鉴“为相关海外 CDN 保留直连路径”的思路，在 Mihomo 中调整规则与 DNS。

具体做法是把微信相关域名的 DIRECT 规则放在前面，涵盖 `wechat.com`、`weixin.qq.com`、`weixin.com`、`qpic.cn` 和 `qlogo.cn`，同时为这些域名配置国内 DoH，并加入 Fake-IP 排除项。另加入参考文章涉及的网段直连例外：

```yaml
- IP-CIDR,43.160.0.0/12,DIRECT,no-resolve
```

域名规则与网段例外共同避免相关连接被后面的通用代理规则接管。`no-resolve` 用于跳过匹配目标 IP 规则时额外触发的域名解析，具体语义见[Mihomo 路由规则](https://wiki.metacubex.one/config/rules/)。

Mihomo 无法识别微信绑定的手机号，这些规则会作用于所有匹配的域名与 IP 流量。`43.160.0.0/12` 范围较宽，也可能影响其他腾讯业务。遇到类似问题时，应先查看实际连接记录，再决定是否加入网段例外。

### 5.2 检查客户端覆写后的实际配置

订阅中的 DNS 不一定就是终端正在使用的 DNS。客户端的全局覆写、TUN 设置或 OpenClash 的配置加工，都可能改变最终结果。

排查时，应同时查看生成 YAML、客户端加载后的配置，以及实际 DNS 和连接记录。特别要确认订阅的是完整配置，并检查 DNS 覆写是否与订阅设置一致。

## 6. 校园网：分别处理认证、DNS 和路由

校园网可能同时提供公网服务、仅校内可访问的服务，以及登录前的认证入口。处理这些场景时，需要确认域名如何解析、目标地址是否可达，以及流量是否命中正确的直连规则。

### 6.1 根据解析结果与重定向确认认证入口

学校域名解析到 `172.16.0.0/12` 等私网地址，说明目标位于私网地址空间。它可能是认证入口、内部业务服务或其他设备，需要结合认证前后的 DNS 结果、HTTP 重定向、DHCP 下发信息及网络管理方说明进一步判断。

系统 HTTP 代理与 TUN 的处理路径也不同：应用可能向代理发送域名，TUN 则接管网络层流量。排查时，应查看实际请求地址、命中规则和出口，避免仅凭 Fake-IP 地址推断白名单是否生效。

### 6.2 多个 DNS 上游不等于按网络位置回退

下面的配置为学校域名指定了两个 DNS 上游：

```yaml
nameserver-policy:
  "+.campus.example.com":
    - 192.0.2.53
    - 119.29.29.29
```

`192.0.2.53` 是用于文档展示的地址，占位表示校园 DNS。这个列表本身不包含“判断是否在校内”的逻辑，也不能保证先使用校园 DNS，再按位置切换到公共 DNS。解析结果还受策略匹配、查询方式、缓存和上游应答影响，参见[Mihomo DNS 解析流程](https://wiki.metacubex.one/config/dns/diagram/)。

如果需要明确区分校内和校外解析，可以分别维护校园与公共网络配置，或在客户端增加可靠的场景切换机制。本文的基础脚本没有实现网络位置检测。

### 6.3 让学校域名跟随当前网络 DNS

对于校内、校外返回不同结果的学校域名，可以尝试使用当前网络下发的系统 DNS，并为认证和内部业务增加直连规则及 Fake-IP 排除项。

下面的片段需要合并到已有配置：将策略项加入 `nameserver-policy`，将域名追加到 `fake-ip-filter`，并把直连规则放在通用代理规则之前。不要用它整体覆盖已有 `dns` 或 `rules`。

```yaml
dns:
  nameserver-policy:
    "+.campus.example.com":
      - system
  fake-ip-filter:
    - "+.campus.example.com"

rules:
  - DOMAIN-SUFFIX,campus.example.com,DIRECT
```

使用前，将示例域名替换成实际学校和认证域名。`system` 应取得当前网络的真实 DNS；如果系统 DNS 指向代理自身，需要先排除循环依赖。仅在校内提供的服务，在校外还需要学校认可的远程访问路径，DNS 设置本身不能建立这条连接。

进入校园网络后，可以先完成认证，再启用完整代理接管。如果认证页打不开，临时停用系统代理或 TUN 做对照，确认认证域名与目标地址后，再添加精确规则。

局域网 NAS 短名同样需要能够解析它的 DNS。DIRECT 只决定连接出口，不会给公共 DNS 增加本地主机记录。

### 6.4 保留 DHCP，检查 IPv6 与 TUN 的实际路径

跨楼宇或多 AP 网络下，终端应保留正常的 DHCP 地址获取。固定某个楼宇的 IPv4 地址，可能影响切换到其他网络后的连接。

IPv6 相关问题应结合实际下发的 DNS 和查询结果排查。直接把 IPv6 DNS 改为公共 DNS，可能失去内部域名解析能力，因此需要先确认业务依赖。

TUN 可以扩大流量接管范围，但具体覆盖情况仍取决于路由、DNS 劫持、绕过规则和其他 VPN。认证失败、内部 DNS 缺失或目标路由不可达，需要分别处理。

## 7. 规则集与状态保存

配置使用六个 ACL4SSR 规则提供者：广告、国内域名、OpenAI、Telegram、Google 和代理域名集合。广告规则使用 REJECT，其他规则按配置导向 DIRECT 或“出口选择”。

规则集通过“出口选择”下载。首次初始化需要有效的代理出口，以及客户端所需的 Geo 数据；新设备应检查规则集是否成功加载。

同时启用以下参数：

```yaml
profile:
  store-selected: true
  store-fake-ip: true
tcp-concurrent: true
```

前两项保存策略组选择和 Fake-IP 映射；`tcp-concurrent` 尝试连接 DNS 解析所得的多个地址，并使用先成功的连接。这些设置有助于保留状态和建立连接，节点本身的可用性仍需通过健康检查和实际业务测试确认。参见[Mihomo 全局配置](https://wiki.metacubex.one/config/general/)。

## 8. 部署后的验证顺序

完成部署后，可以按“服务入口—订阅下载—配置加载—业务连接”的顺序验证，避免把某一层成功当作整条链路正常。

### 8.1 验证两个服务入口

分别访问 NAS 的 LAN 和 ZeroTier 地址，确认 Sub-Store 首页可打开。再通过对应入口取得生成文件，检查响应是否为 YAML，而不是错误信息或网页内容。

### 8.2 检查完整配置与规则集

在客户端更新完整配置，检查运行模式是否为 `rule`，策略组成员是否存在，以及六个规则提供者是否加载成功。

使用 Mihomo 命令行时，可以先校验配置：

```bash
mihomo -t -f config.yaml
```

配置中使用 `geosite` 和 `GEOIP` 时，需要准备客户端所需的 Geo 数据。OpenClash 用户应在其配置管理中完成校验，并检查加工后的活动配置。

### 8.3 查看实际连接与业务效果

在“出口选择”中选定目标组，检查普通组是否取得预期的 204，AI 组是否取得预期的 401。随后访问实际业务，查看客户端连接记录中的规则和出口。

微信场景应测试图片加载，并确认相关连接走 DIRECT；AI 场景应验证实际账号功能；校园场景应分别测试认证页、学校公网服务和内部服务。

配置校验能够发现语法与引用问题，端点测试能够检查连通性，实际业务测试才能说明使用效果。排查结果还应记录所处网络、选择的出口和测试时间，便于后续对照。

## 附录 A：完整部署配置

下面提供前后端合并、LAN 与 ZeroTier 双地址访问的完整部署示例。数据目录使用持久化挂载，重启策略设为 unless-stopped。新部署可以按此创建；已有服务应先备份数据，并核对原有环境变量和端口。

本文使用的后端版本为 `2.42.2`。`latest` 标签会随镜像更新变化，部署时应记录实际运行版本。镜像的路径前缀与合并模式说明见[维护者 Docker 文档](https://hub.docker.com/r/xream/sub-store)。

### A.1 docker-compose.yml

```yaml
services:
  sub-store:
    image: xream/sub-store:latest
    container_name: sub-store
    restart: unless-stopped
    environment:
      SUB_STORE_BACKEND_MERGE: "true"
      SUB_STORE_FRONTEND_BACKEND_PATH: "${SUB_STORE_BACKEND_PATH:?请设置私人后端路径}"
      SUB_STORE_CORS_ALLOWED_ORIGINS: "http://${NAS_LAN_IP}:3002,http://${NAS_ZT_IP}:3002"
      TIME_ZONE: Asia/Shanghai
    ports:
      - "${NAS_LAN_IP}:3002:3000"
      - "${NAS_ZT_IP}:3002:3000"
    volumes:
      - ./sub-store-data:/opt/app/data
```

### A.2 .env.example

```dotenv
# 地址均为虚构示例，请替换为 NAS 的实际地址。
NAS_LAN_IP=192.168.10.20
NAS_ZT_IP=192.168.200.20
# 用新生成的长随机字母数字串替换此示例，保留开头的 /。
SUB_STORE_BACKEND_PATH=/REPLACE_WITH_A_LONG_RANDOM_PRIVATE_PATH
```

把 `.env.example` 复制成同目录 `.env`，替换两项地址与后端路径。ZeroTier 地址必须已存在于 NAS 的接口上。

这里列出了两个前端来源。CORS 只是浏览器跨源访问控制，不能代替服务访问控制；示例后端路径也必须换成自己的长随机值。订阅链接仍按私人数据处理。

部署目录示例：

```text
sub-store-public/
├── docker-compose.yml
├── .env
└── sub-store-data/
```

在该目录运行：

```bash
docker compose config --quiet
docker compose up -d
```

前端使用 `http://NAS地址:3002/`，后端地址使用 `http://NAS地址:3002/自己的私人路径`。在前端创建“示例订阅”，填写自己的上游链接；下载代理按实际需要配置，不能照搬示例路由器地址。

## 附录 B：完整 Sub-Store 文件生成脚本

在 Sub-Store 的“文件”功能中选择订阅来源，节点输出使用 ClashMeta，再增加启用的、本地内容模式的 `Script Operator`。脚本处理的是节点 YAML，不是逐个节点对象。

脚本根据节点名称生成策略组，并写入测速参数、规则集、DNS 和运行设置。默认使用 7890 混合端口和 1053 DNS 端口，均仅在本机监听，适合单机客户端。用于 OpenClash 时，应核对其实际端口与监听设置。

修改地区或运营商命名时，调整脚本中的 `regions` 和 `carriers`。更改组名还需要同步修改规则、规则集下载出口及 DNS 引用。

```javascript
// Sub-Store 文件脚本：从 ClashMeta 节点生成完整 Mihomo 配置。
// 地区/运营商正则为便于复用的示例；按自己的节点命名调整。
// 输入应是 Sub-Store 已转换成 ClashMeta 的节点 YAML。
// 在“文件”的本地 Script Operator 中使用，避免放到“单节点操作”里。
const yaml = ProxyUtils.yaml;
const source = yaml.safeLoad($content || $files[0]) || {};
const proxies = source.proxies;
if (!Array.isArray(proxies) || proxies.length === 0) {
  throw new Error("输入没有代理节点，请检查来源及 ClashMeta 格式");
}
const regions = [
  ["香港", /香港|HK|Hong\s*Kong/i],
  ["台湾", /台湾|台灣|TW|Taiwan/i],
  ["日本", /日本|JP|Japan/i],
  ["新加坡", /新加坡|SG|Singapore/i],
  ["美国", /美国|美國|US|United\s*States/i],
];
const carriers = [
  ["移动", /移动|移動|CMCC|CMI|\bCM\b/i],
  ["联通", /联通|聯通|Unicom|4837|9929|CUG|\bCU\b/i],
  ["电信", /电信|電信|Telecom|CN2|163|\bCT\b/i],
];
const reserved = new Set(["DIRECT", "REJECT", "GLOBAL", "出口选择",
  "手动选择", "移动优选", "联通优选", "电信优选", "AI-移动优选"]);
for (const [r] of regions) for (const [c] of carriers.slice(0, 2)) {
  reserved.add(r + "-" + c);
}
for (const r of ["香港", "新加坡", "美国"]) reserved.add("AI-" + r + "-移动");
const names = new Set();
for (const p of proxies) {
  if (typeof p.name !== "string" || !p.name.trim() ||
      names.has(p.name) || reserved.has(p.name)) {
    throw new Error("节点名为空、重复或与策略组/内置名称冲突");
  }
  names.add(p.name);
}
const config = {
  "mixed-port": 7890,
  "allow-lan": false,
  "bind-address": "127.0.0.1",
  "log-level": "info",
  "ipv6": false,
  "rule-providers": {
    "acl4ssr-ban-ad": {
      "type": "http",
      "behavior": "classical",
      "format": "text",
      "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanAD.list",
      "path": "./ruleset/acl4ssr-ban-ad.list",
      "interval": 86400,
      "proxy": "出口选择"
    },
    "acl4ssr-china-domain": {
      "type": "http",
      "behavior": "classical",
      "format": "text",
      "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaDomain.list",
      "path": "./ruleset/acl4ssr-china-domain.list",
      "interval": 86400,
      "proxy": "出口选择"
    },
    "acl4ssr-openai": {
      "type": "http",
      "behavior": "classical",
      "format": "text",
      "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/OpenAi.list",
      "path": "./ruleset/acl4ssr-openai.list",
      "interval": 86400,
      "proxy": "出口选择"
    },
    "acl4ssr-telegram": {
      "type": "http",
      "behavior": "classical",
      "format": "text",
      "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/Telegram.list",
      "path": "./ruleset/acl4ssr-telegram.list",
      "interval": 86400,
      "proxy": "出口选择"
    },
    "acl4ssr-google": {
      "type": "http",
      "behavior": "classical",
      "format": "text",
      "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/Google.list",
      "path": "./ruleset/acl4ssr-google.list",
      "interval": 86400,
      "proxy": "出口选择"
    },
    "acl4ssr-proxy-gfw": {
      "type": "http",
      "behavior": "classical",
      "format": "text",
      "url": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ProxyGFWlist.list",
      "path": "./ruleset/acl4ssr-proxy-gfw.list",
      "interval": 86400,
      "proxy": "出口选择"
    }
  },
  "rules": [
    "DOMAIN-SUFFIX,wechat.com,DIRECT",
    "DOMAIN-SUFFIX,weixin.qq.com,DIRECT",
    "DOMAIN-SUFFIX,weixin.com,DIRECT",
    "DOMAIN-SUFFIX,qpic.cn,DIRECT",
    "DOMAIN-SUFFIX,qlogo.cn,DIRECT",
    "IP-CIDR,43.160.0.0/12,DIRECT,no-resolve",
    "DOMAIN-SUFFIX,chatgpt.com,出口选择",
    "DOMAIN-SUFFIX,openai.com,出口选择",
    "DOMAIN-SUFFIX,oaistatic.com,出口选择",
    "DOMAIN-SUFFIX,oaiusercontent.com,出口选择",
    "DOMAIN-SUFFIX,sora.com,出口选择",
    "RULE-SET,acl4ssr-openai,出口选择",
    "DOMAIN,nas.example.com,DIRECT",
    "DOMAIN-SUFFIX,gov.cn,DIRECT",
    "DOMAIN-SUFFIX,campus.example.com,DIRECT",
    "DOMAIN-SUFFIX,lan,DIRECT",
    "DOMAIN-SUFFIX,local,DIRECT",
    "DOMAIN-SUFFIX,home.arpa,DIRECT",
    "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
    "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
    "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,169.254.0.0/16,DIRECT,no-resolve",
    "IP-CIDR6,fc00::/7,DIRECT,no-resolve",
    "IP-CIDR6,fe80::/10,DIRECT,no-resolve",
    "IP-CIDR6,::1/128,DIRECT,no-resolve",
    "RULE-SET,acl4ssr-ban-ad,REJECT",
    "RULE-SET,acl4ssr-telegram,出口选择",
    "RULE-SET,acl4ssr-google,出口选择",
    "RULE-SET,acl4ssr-proxy-gfw,出口选择",
    "RULE-SET,acl4ssr-china-domain,DIRECT",
    "GEOIP,CN,DIRECT,no-resolve",
    "MATCH,出口选择"
  ],
  "mode": "rule",
  "dns": {
    "enable": true,
    "ipv6": false,
    "enhanced-mode": "fake-ip",
    "fake-ip-range": "198.18.0.1/16",
    "fake-ip-filter": [
      "geosite:cn",
      "*.wechat.com",
      "*.weixin.qq.com",
      "*.weixin.com",
      "*.qpic.cn",
      "*.qlogo.cn"
    ],
    "respect-rules": true,
    "default-nameserver": [
      "119.29.29.29"
    ],
    "proxy-server-nameserver": [
      "https://dns.alidns.com/dns-query",
      "https://doh.pub/dns-query"
    ],
    "nameserver": [
      "https://dns.google/dns-query#出口选择",
      "https://cloudflare-dns.com/dns-query#出口选择"
    ],
    "nameserver-policy": {
      "geosite:cn,private": [
        "https://dns.alidns.com/dns-query",
        "https://doh.pub/dns-query"
      ],
      "+.chatgpt.com": [
        "https://dns.google/dns-query#出口选择",
        "https://cloudflare-dns.com/dns-query#出口选择"
      ],
      "+.openai.com": [
        "https://dns.google/dns-query#出口选择",
        "https://cloudflare-dns.com/dns-query#出口选择"
      ],
      "+.oaistatic.com": [
        "https://dns.google/dns-query#出口选择",
        "https://cloudflare-dns.com/dns-query#出口选择"
      ],
      "+.oaiusercontent.com": [
        "https://dns.google/dns-query#出口选择",
        "https://cloudflare-dns.com/dns-query#出口选择"
      ],
      "+.wechat.com": [
        "https://dns.alidns.com/dns-query",
        "https://doh.pub/dns-query"
      ],
      "+.weixin.qq.com": [
        "https://dns.alidns.com/dns-query",
        "https://doh.pub/dns-query"
      ],
      "+.weixin.com": [
        "https://dns.alidns.com/dns-query",
        "https://doh.pub/dns-query"
      ],
      "+.qpic.cn": [
        "https://dns.alidns.com/dns-query",
        "https://doh.pub/dns-query"
      ],
      "+.qlogo.cn": [
        "https://dns.alidns.com/dns-query",
        "https://doh.pub/dns-query"
      ]
    },
    "listen": "127.0.0.1:1053"
  },
  "profile": {
    "store-selected": true,
    "store-fake-ip": true
  },
  "tcp-concurrent": true
};
config.proxies = proxies;
const tests = [];
function addTest(name, predicate, ai = false) {
  const members = proxies.filter(predicate).map(p => p.name);
  if (!members.length) return; // 无节点的组不会进入最终选择器
  tests.push({
    name, type: "url-test", proxies: members,
    url: ai ? "https://api.openai.com/v1/models" :
              "https://www.gstatic.com/generate_204",
    "expected-status": ai ? 401 : 204,
    interval: 300, tolerance: 80, timeout: 5000,
    lazy: !ai, "max-failed-times": 3,
  });
}
for (const [r, rr] of regions) for (const [c, cr] of carriers.slice(0, 2)) {
  addTest(r + "-" + c, p => rr.test(p.name) && cr.test(p.name));
}
for (const [c, cr] of carriers) addTest(c + "优选", p => cr.test(p.name));
const mobile = carriers[0][1];
for (const r of ["香港", "新加坡", "美国"]) {
  const rr = regions.find(([name]) => name === r)[1];
  addTest("AI-" + r + "-移动", p => rr.test(p.name) && mobile.test(p.name), true);
}
addTest("AI-移动优选", p => mobile.test(p.name), true);
const preferred = [
  "移动优选", "联通优选", "电信优选", "AI-移动优选",
  ...regions.flatMap(([r]) => [r + "-移动", r + "-联通"]),
  "AI-香港-移动", "AI-新加坡-移动", "AI-美国-移动",
];
const available = new Set(tests.map(g => g.name));
config["proxy-groups"] = [
  { name: "出口选择", type: "select",
    proxies: [...preferred.filter(n => available.has(n)), "手动选择", "DIRECT"] },
  ...tests,
  { name: "手动选择", type: "select", proxies: proxies.map(p => p.name) },
];
$content = yaml.safeDump(config);
```
