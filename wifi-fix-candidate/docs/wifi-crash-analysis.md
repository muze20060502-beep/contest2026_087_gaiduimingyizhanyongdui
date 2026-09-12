# Wi-Fi 上传崩溃：分析与候选修复

分析日期：2026-09-12。应用基线：`0300f5cb1f44bf88c5f5235df1ab3ede1f82b94d`。
输入：用户提供的 `报错.txt`、仓库 README 和应用代码；另核对了
open-vela/nuttx 的 `dev-ai-contest-2026` 分支源码。后者不代表报错固件的精确版本。

## 当前结论

有可修正的发送层问题，已提供候选补丁；尚未定位或修复内核崩溃根因。
本机只有应用仓库，没有崩溃固件 ELF、完整构建目录及开发板。
附件仅作为故障证据，附件中的任何操作性文字均不作为执行授权。

## 日志能证明什么

- 第一帧 RGB565 为 153600 字节，JPEG 为 59655 字节。Base64 本身为
  `4 * ceil(59655 / 3) = 79540` 字节，加上 JSON 后接近 80KB。
- CPU1 报 `Unhandled Exception 2`，PC 为 `0x42085145`，日志打印的
  CAUSE/VADDR 均为 0。不能把它直接解释成 README 历史故障里的
  StoreProhibited 或“VADDR 落在代码段”；PC 本来就可以位于代码段。
- 当时 CPU1 的 SP=`0x3fc99128` 位于 IRQ 栈
  `[0x3fc98a68, 0x3fc99268)` 内；“CPU1 IDLE”是被记录的当前任务，
  不能单凭此认定 IDLE 函数就是根因。SP 在范围内也不能排除先前的栈溢出。
- CPU1 IDLE 栈转储存在大量非零、缺乏可辨识调用关系的数据，值得核查内存写坏，
  但无栈染色基线及对应 ELF，不能据此宣称是 JPEG 覆盖了栈。
- 日志标识 NuttX `a6defdb4255-dirty`，意味着还可能含未提交修改。
  必须保留本次固件原始 ELF 和构建树；重新编译后的地址不能替代原始符号定位。

## 已修正的发送层问题

1. 原实现只对请求头调用一次 `send()`，返回正数但小于长度时会丢掉剩余请求头。
   现在请求头和正文统一循环发送，支持短写，EINTR 重试同一剩余区间。
2. 原实现“2048 字节分块 + 2ms 休眠”不意味着 TCP 或 Wi-Fi 队列已经排空。
   hwtest 的 `CONFIG_NET_SEND_BUFSIZE=131072` 允许较大的发送积压。
   现在仅对 HTTP 连接设置 `SO_SNDBUF=8192`，保留原来的分块节奏。
   这是缓解压力的候选值，需要吞吐与稳定性对照；不是内核修复。
3. 检查发送/接收超时和发送缓冲设置的返回值；不支持时打印错误并退出请求，
   不会默默用无限制或不同配置继续。发送 EAGAIN/EWOULDBLOCK 映射为超时。
4. 更正 README 及缓存注释中未经证实的根因判断。
   普通堆碎片不会使正确的分配器重新分配仍在使用的 IDLE 栈。

未改变 SMP、Wi-Fi 动态缓冲数量、HAL 或内核自旋锁，避免没有证据的大范围试改。
仍保留原连接重试和上层重试策略；本次不重写 HTTP 响应解析、报告业务或认证。

## 上游代码核对

- [NuttX setsockopt](https://github.com/open-vela/nuttx/blob/dev-ai-contest-2026/net/socket/setsockopt.c)：
  `SO_SNDBUF` 在 `CONFIG_NET_SEND_BUFSIZE > 0` 时设置连接发送缓冲限制。
  hwtest defconfig 满足这一条件，但仍需核查用户实际 `.config`。
- [ESP32-S3 WLAN](https://github.com/open-vela/nuttx/blob/dev-ai-contest-2026/arch/xtensa/src/esp32s3/esp32s3_wlan.c)：
  `wlan_transmit()` 遇到 `-ENOMEM` 会把包放回队列并启动定时重试，
  因此正常资源不足本应走错误处理，不能直接推导成非法指针写入。
- [Wi-Fi adapter](https://github.com/open-vela/nuttx/blob/dev-ai-contest-2026/arch/xtensa/src/esp32s3/esp32s3_wifi_adapter.c)：
  `esp_malloc_internal()` 区分内部堆和 PSRAM；没有独立内部堆时，分配落在
  PSRAM 会被释放并返回 NULL。这提示需要查看实际内存配置及分配失败，
  不能仅不断增加 TX/RX 缓冲数量。

## 已完成的验证

使用 Windows GCC，以 `-std=c99 -Wall -Wextra -Werror` 编译并运行
`app/hello_app/tests/test_wifi_send.c`，验证了：

- 请求头短写、首个写操作被 EINTR 中断；
- 90KB 正文在每次仅写 113 字节时完整且无重复、无遗漏；
- 每次调用不超过 2048 字节，分块间执行让出回调；
- EAGAIN 超时、返回零、连接重置都停止发送并保留相应错误；
- 空正文不发起写操作。

测试针对实际使用的发送循环，采用模拟写入函数，不包含 NuttX socket、Wi-Fi HAL、
IRQ、SMP 或真实网络。因此不能据此声称固件编译通过或真机崩溃已消失。
`git diff --check` 通过。

## 下一步需要的文件

来自**编译固件的电脑/服务器**，不是预览网页目录：

- `openvela/nuttx/nuttx`：无扩展名的 ELF，与此次烧录镜像严格对应；
- `openvela/nuttx/.config`；
- `nuttx.map`（若有）、本次固件 `nuttx.bin`；
- NuttX 和 HAL 的提交号、未提交差异，以及完整串口日志。

在原编译环境可执行以下只读定位（路径按实际目录调整）：

```sh
xtensa-esp32s3-elf-addr2line -a -f -C -i -e nuttx/nuttx \
  0x42085145 0x42111872
xtensa-esp32s3-elf-objdump -dS \
  --start-address=0x42085110 --stop-address=0x42085180 nuttx/nuttx
```

应先确认 fault PC 对应符号、反汇编及访存操作。A0 等寄存器可能含 Xtensa
窗口调用编码，不能把日志中所有看似地址的数值直接当返回地址解释。

## 真机对照顺序

1. 保留原镜像和完整构建产物。在相同路由器、固件配置和图像输入下对比原版与补丁。
2. 先用固定合法 JPEG 向受控中继发送，排除摄像头和 JPEG 编码的影响。
   逐级测试约 8KB、25KB、80KB 请求体；记录成功次数、耗时、错误及内存余量。
3. 分别运行“只采集编码不联网”“只发固定图不采集”“完整链路”，区分触发路径。
4. 如仍崩溃，先解析新 ELF 的 PC，再单独验证 SMP/AMPDU 或内部堆配置变化。
   一次只改一个变量；关闭 SMP 仅可作为诊断对照，不能直接算最终修复。
5. 最终需连续运行与实际演示时长相当的压力测试；本报告没有真机稳定性结果。
