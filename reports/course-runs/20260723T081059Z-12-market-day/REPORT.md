# Mini-HFT Market Day Evidence Report

- RUN_ID: `20260723T081059Z-12-market-day`
- Evidence root: `/financial-low-latency/Documents/reports/course-runs/20260723T081059Z-12-market-day`

## Phase evidence

| Phase | Raw file | SHA-256 | Application summary |
| --- | --- | --- | --- |
| OPEN | `raw/01-data-path.txt` | `de357992681fc1d4d1e0c1ca9134cc841617a9c0deba6b02eafc28fe49e781a1` | `raw output` |
| OPEN | `raw/01-eos-enable.txt` | `8247bfde564eba994066fde8b6c44b4f58aac0ccbc9136d289482f79aa0138b1` | `raw output` |
| OPEN | `raw/01-eos-preflight.txt` | `f137621ac20377979a727419f1ca59927222e2530025d9bb6ff8791580b55d50` | `raw output` |
| OPEN | `raw/01-services-start.txt` | `1960ad058a8d95a616bbea675793c60635b02b61fa140d27a416b3792e0f3dc3` | `raw output` |
| OPEN | `raw/01-services-status.txt` | `ca53842c299d1ed21061e3be9b4db51ee22d8d55b4809510479c984afb1ebc30` | `raw output` |
| OPEN | `raw/01-trex-open.txt` | `c9b33d6e54ed93c51df9b81eaea3e6ac450bd450eeeec2f3dacb1c4c03f428bb` | `raw output` |
| OPEN | `raw/01-trex-prepare.json` | `266d870e804eea8c9fe860e73a7c5f4ae0d34a5d5b6d785a49e87dee599a8ded` | `raw output` |
| OPEN | `raw/01-trex-status.txt` | `bdddda36f70b86c01b0cacd157a9713ce02d0ac06aa9c85ff7cfb765316880a4` | `raw output` |
| CALM | `raw/02-calm-api.txt` | `a28bb7e01585aaddcd14431a9fd1b56ba41e4e2ac8308f3fba750dfb84ab55a4` | `raw output` |
| CALM | `raw/02-calm-eos-after.txt` | `6fad61e431a16df87e8af9822fd240bc98c798554f2af0d54c52e75dbefbce21` | `raw output` |
| CALM | `raw/02-calm-eos-before.txt` | `74d41fb8131c00f15151c4db553977921b1441306c9de749d31589adfbda95e2` | `raw output` |
| CALM | `raw/02-calm-exchange.txt` | `46800831117d18cc9b21d4210f777853ee038c782d8984723c5a894b32319f08` | `event=summary node=vm-2522-01 monotonic_ns=24127115584379 run_id=20260723T081059Z-12-market-day phase=CALM ticks_sent=32 orders_applied=1 correlation=690074870` |
| CALM | `raw/02-calm-nic-after.txt` | `1470d783699af8b674a5c456e49d7f8f1baf833a67dfab49656441e1435385a2` | `raw output` |
| CALM | `raw/02-calm-nic-before.txt` | `c51bd6b455652fd177190af65439228e904faf2d85e1a863489383c27cc41554` | `raw output` |
| CALM | `raw/02-calm-pressure-event.json` | `fdabc5f0ea13650e1cf76821af3ec962ae2c4056431ddb44eaf4cc9ab41ca77f` | `raw output` |
| CALM | `raw/02-calm-trader.txt` | `848ea77b06d9569419ee743e60a5a4f2df5baed34febc8083560a5f0677d1ae3` | `event=summary node=vm-2522-02 monotonic_ns=24125094794872 run_id=20260723T081059Z-12-market-day phase=CALM ticks_received=32 unique=32 duplicate=0 gap_remaining=none tick_window_ns=157523386 order_actions=1 correlation=690074870` |
| CALM | `raw/02-calm-trex-console.txt` | `731929f7c5deac16da1fb865329bf3b44e7313c5ee8926c5cb3be99255c9bf21` | `raw output` |
| CALM | `raw/02-calm-trex.json` | `47c35c6b14b493d2d7cfa730a2aec80d426a02323743834ad00c3c2d181bf521` | `raw output` |
| BURST | `raw/03-burst-api.txt` | `045466d8e805c0713f260c88657c316456d4dde3e4bb91d9cea94bb91f78c728` | `raw output` |
| BURST | `raw/03-burst-eos-after.txt` | `bc08d0ae45bc4c51acefefe03c2f7c7622057e5c0329bfe4d3f9b7ee319f516d` | `raw output` |
| BURST | `raw/03-burst-eos-before.txt` | `bc199da6eeb5119dabf24f5feaebfbc9abc62bad4acf554276adcbf12c02063f` | `raw output` |
| BURST | `raw/03-burst-exchange.txt` | `efcc2399075ee0456990d0660d8cb66e672024c17a573237ff70ca95a23497ef` | `event=summary node=vm-2522-01 monotonic_ns=24162082899899 run_id=20260723T081059Z-12-market-day phase=BURST ticks_sent=32 orders_applied=1 correlation=3390133280` |
| BURST | `raw/03-burst-nic-after.txt` | `74f158cddbba26adf439f864d6557be50204b3fb7844af9407b3846f956c8e4d` | `raw output` |
| BURST | `raw/03-burst-nic-before.txt` | `2bb385dc3a8a205505f071fdd3cfcfe5234a9dab29bf78ef2d748bb2858b1d65` | `raw output` |
| BURST | `raw/03-burst-pressure-event.json` | `fbb422a24e2d400135be2680151a0a550b974ff4140205f1ebb8eaac3762949e` | `raw output` |
| BURST | `raw/03-burst-trader.txt` | `442064ffb10d25b876f4877672111baacfaff171676a6f862255a08e6c2f6f48` | `event=summary node=vm-2522-02 monotonic_ns=24160061621850 run_id=20260723T081059Z-12-market-day phase=BURST ticks_received=32 unique=32 duplicate=0 gap_remaining=none tick_window_ns=1113332 order_actions=1 correlation=3390133280` |
| BURST | `raw/03-burst-trex-console.txt` | `9eb79a78564a77e4e74101069e8824ca06799a1f6cb2cd3f0df568b368f7681c` | `raw output` |
| BURST | `raw/03-burst-trex.json` | `369dc764865d474658e7c4e0fcea03929ba224b33f855c8c4e1ff6b8260b029f` | `raw output` |
| FAULT | `raw/04-fault-api.txt` | `952d10ca30c3064f9bf8cd13d3a4c9223b58949863f1c08035c6e9f1a8ad55d9` | `raw output` |
| FAULT | `raw/04-fault-eos-after.txt` | `26932728ca7903aca4e27280875782377cd4d2e990f4e9658073d72de14c69ac` | `raw output` |
| FAULT | `raw/04-fault-eos-before.txt` | `cec22c5de78d2a9baf8706130deaf7e72a6bc3bccc246fe37030806d7e9d1122` | `raw output` |
| FAULT | `raw/04-fault-exchange.txt` | `64fbb0a6c56bc60ea3454d0e0e7fc4c2afc4c310d26b4713364f242c2aaab2a9` | `event=summary node=vm-2522-01 monotonic_ns=24192092183679 run_id=20260723T081059Z-12-market-day phase=FAULT ticks_sent=15 orders_applied=1 correlation=687811123` |
| FAULT | `raw/04-fault-nic-after.txt` | `98bbe06a340124da1fecc9247d60c7058e42adca34a638e1a5a40995448d1da4` | `raw output` |
| FAULT | `raw/04-fault-nic-before.txt` | `3cd227de757a8f3e87de41872b14103a804058a121d27834f25ceb1709b4aff8` | `raw output` |
| FAULT | `raw/04-fault-terminal-state.json` | `35e0b262296b02ce473f900b8f4fb6923dd946ccec92411e48878e71eecd28a9` | `raw output` |
| FAULT | `raw/04-fault-trader.txt` | `2688f673f0759181e2851d108fddc0b67b2340acfe74fe987d2cc1efdb2615ca` | `event=summary node=vm-2522-02 monotonic_ns=24190070549729 run_id=20260723T081059Z-12-market-day phase=FAULT datagrams_received=15 unique=8 duplicate=7 sequence4_source=B gap_remaining=none order_actions=1 correlation=687811123` |
| FAULT | `raw/04-fault-trex-lease.txt` | `18918fa65417ec140a170c66dddc97ce11c1fc00caaf5be364950a78c6fe6b5d` | `raw output` |
| FAULT | `raw/04-fault-trex-status.txt` | `1ae26e99438fef494f6a05a99a27b1be6bfe909c6df04db8b9cf80ffa6d571e2` | `raw output` |
| RECOVER | `raw/05-onload-exchange.txt` | `b91bccf89ca5f8b03d33082f47df9a988b8c81f1837b2ffad4f1c14969337476` | `raw output` |
| RECOVER | `raw/05-onload-trader.txt` | `e3c4872970082d275f83b87a17b9867911f50b49f2401d2c57cadfe942b9ec42` | `raw output` |
| RECOVER | `raw/05-order-api-replay.json` | `c23c3ef1ca54787c66e80dea189587eb5344fef5c74865eb1994e2bf4247103c` | `raw output` |
| RECOVER | `raw/05-order-api.json` | `ea3a5831948dea15291f435b58cf5e65c8fb84169e1676dc1ab3b35d0875fb9d` | `raw output` |
| RECOVER | `raw/05-order-ui.json` | `60f13a0738e42bf2cc9f31444c7a1110f4823fa15e7be07afea9c641533a9b01` | `raw output` |
| RECOVER | `raw/05-recover-exchange.txt` | `e5e26e3882bb55c866ecea29c7c2e23206ecf40263366d8968f6ace85c400699` | `event=summary node=vm-2522-01 monotonic_ns=24216746533481 run_id=20260723T081059Z-12-market-day phase=RECOVER connections=2 unique_correlations=1 action_count=1` |
| RECOVER | `raw/05-recover-ingest.txt` | `3a90b11dfb4916ed380618ed7157daea2f075270b7e9c6e18a2c75608f7305ac` | `raw output` |
| RECOVER | `raw/05-recover-phase.json` | `98a440f5b36bab3efd53b8eafcbe0515623c712c2209789f3d9c2c9e5ccc1a55` | `raw output` |
| RECOVER | `raw/05-recover-trader-g1.txt` | `9424827b6d998d3f858c87e7213b9048e32aa52d828e820c581e1f471d1dd2d0` | `raw output` |
| RECOVER | `raw/05-recover-trader-g2.txt` | `ceeddbdc2a54f4db895328ac73b02f62ce02594633b1f9922e5a4d0080a1e173` | `event=summary node=vm-2522-02 monotonic_ns=24214724523894 run_id=20260723T081059Z-12-market-day phase=RECOVER generation=2 correlation=2431909399 responses=ACK,EXECUTION` |
| RECOVER | `raw/05-recover-trex-lease.txt` | `fd25923a6d09124e9475a1fba2d064e6c20fbd5086baad1240a939a719e950e3` | `raw output` |
| RECOVER | `raw/05-sse-disconnect.txt` | `78f9a9799f58dde6839b40d7fcae9d99daf918e6f525cb05585497dc17f848f9` | `raw output` |
| RECOVER | `raw/05-terminal-state.json` | `0292a0a86db5839fb72551b23928717bb1aea309a63fa5d5b861872f97679876` | `raw output` |
| CLOSE | `raw/06-close-api.json` | `51c3a9f42bbec5e93b367afd92ba17602525efaa084841fc8127c3c4660cf764` | `raw output` |
| CLOSE | `raw/06-close-terminal-state.json` | `377c8c38a4ee20785afc76ab02d818a8d46a4b180a82d670e3d09318899d7586` | `raw output` |
| CLOSE | `raw/06-eos-disable.txt` | `04357040984b5b3b4bda277813f4f0a61e8b6b3ef51fa6483de6c14534e621a6` | `raw output` |
| CLOSE | `raw/06-remote-remove.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `raw output` |
| CLOSE | `raw/06-services-stop.txt` | `6fe422ed39adea756efbc69b67f1843a7903e9431efc2e062586ad0975e339cd` | `raw output` |
| CLOSE | `raw/06-trex-recover.txt` | `9a71146d66599d2c9af5dac596a8d793e4487b65665a0fe18f362e0fc4290408` | `raw output` |
| CLOSE | `raw/06-vm1-remote/burst-exchange-39183.pid` | `97a5385f8de4feffaa1b979feec9215f6328dc30ccc1506aa9eac6b51cc272d4` | `raw output` |
| CLOSE | `raw/06-vm1-remote/calm-exchange-39123.pid` | `1cbe3a5e0aed8258fb7bd2259d2557cff77e2dda05e09c5e73265786e46f8709` | `raw output` |
| CLOSE | `raw/06-vm1-remote/fault-exchange-39232.pid` | `1b672faaf2999dffe4b124bf18527aa639adbcfbb771c6eae4da70f8448614a1` | `raw output` |
| CLOSE | `raw/06-vm1-remote/market_day.py` | `427e72c939ede0b726ec7a8f899a1564da9a537533249e59660ba7e8a7fbf431` | `raw output` |
| CLOSE | `raw/06-vm1-remote/order-service/requests.ndjson` | `c60d818665dc9317aef77191b49961c25a1269baad6460d0a43c5ac3828f5f23` | `raw output` |
| CLOSE | `raw/06-vm1-remote/order-service/state.json` | `f2052359970c1153e3228dcd2eb2616e2d2e6ae9be0b2e77d45e64c7b048588a` | `raw output` |
| CLOSE | `raw/06-vm1-remote/order.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `raw output` |
| CLOSE | `raw/06-vm1-remote/order.stdout` | `61c6e5ad9d5260e110484ca3351f344d2ef7788020107c609ab5ee6efebfdaa7` | `raw output` |
| CLOSE | `raw/06-vm1-remote/order_service.py` | `5967055febd623765d03c0dc1fd2ebb67d097182b26cd7b9aa7a7cccdb59f129` | `raw output` |
| CLOSE | `raw/06-vm1-remote/recover-exchange-39281.pid` | `37dd8c354dfc66887be5d2177bdd1dcffef97ac23220f45a91c5ffd20120baed` | `raw output` |
| CLOSE | `raw/06-vm101-baseline.txt` | `7cd376bccf70fb824774726fd08da557d3de38e8e94365df623a921b218a5252` | `raw output` |
| CLOSE | `raw/06-vm101-remote/gateway/commands.ndjson` | `0b94910c3ede4b467286f1f29416327632ce285dc6fed5c098e560a904d9491f` | `raw output` |
| CLOSE | `raw/06-vm101-remote/gateway/events.ndjson` | `b3ae5bf972db02f938aaa21a4f996843aeac465dd666f70dddcdaae404181a97` | `raw output` |
| CLOSE | `raw/06-vm101-remote/gateway/state.json` | `be1cfe8676d24115c9838fa27efbcc0e7b66f8fdc9d7d80ce71b5f8cf4377704` | `raw output` |
| CLOSE | `raw/06-vm101-remote/gateway.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `raw output` |
| CLOSE | `raw/06-vm101-remote/gateway.stdout` | `207d066e106a9027d48d6808ad30ffbdf46140e1f35c90d413ba91ee5f5d97ac` | `raw output` |
| CLOSE | `raw/06-vm101-remote/terminal/index.html` | `3845c0f4360dd9349a39eaa25da6f7addf6e837bf8f565b22290859f2f91c9c6` | `raw output` |
| CLOSE | `raw/06-vm101-remote/terminal/terminal.css` | `c1161237fd093c044d13fad929e3ea577fac2c04151ed1c25a4822845a33b3e9` | `raw output` |
| CLOSE | `raw/06-vm101-remote/terminal/terminal.js` | `e70bf2ba5c255c8e637a2402e5d19fdcc18a536d3d49d737c0130982a3a9ab7e` | `raw output` |
| CLOSE | `raw/06-vm101-remote/terminal_gateway.py` | `2c11abd3c2697050f2310dea6e66c4bad38c341a748a84be9c7d9648d16f2558` | `raw output` |
| CLOSE | `raw/06-vm11-baseline.txt` | `c097c8f9ed54021a5a112baae4428c29f0657e84ab402819d8f6bb5339905dba` | `raw output` |
| CLOSE | `raw/06-vm11-remote/bind.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `raw output` |
| CLOSE | `raw/06-vm11-remote/market_trex_client.py` | `b8afe256b3d88a21abbee44753e2b77e11ec07608d4518389c6e7445bbd0343e` | `raw output` |
| CLOSE | `raw/06-vm11-remote/market_trex_control.sh` | `1f0abc9377338ebace6b640c2af6e7db8195031ce86078c652d6b9c3582561ac` | `raw output` |
| CLOSE | `raw/06-vm11-remote/server.log` | `d33e2fa5465c4739507a21fb6900fe507ba1e305e906b583c3e77dfa6b732514` | `raw output` |
| CLOSE | `raw/06-vm11-remote/trex-burst.json` | `369dc764865d474658e7c4e0fcea03929ba224b33f855c8c4e1ff6b8260b029f` | `raw output` |
| CLOSE | `raw/06-vm11-remote/trex-calm.json` | `47c35c6b14b493d2d7cfa730a2aec80d426a02323743834ad00c3c2d181bf521` | `raw output` |
| CLOSE | `raw/06-vm11-remote/trex-dual.yaml` | `017adf5bbd266ecd700d8150ceb06e6fedcf05cf28d21620487afe7ae4786e77` | `raw output` |
| CLOSE | `raw/06-vm11-remote/trex-prepare.json` | `266d870e804eea8c9fe860e73a7c5f4ae0d34a5d5b6d785a49e87dee599a8ded` | `raw output` |
| CLOSE | `raw/06-vm2-remote/adapter.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `raw output` |
| CLOSE | `raw/06-vm2-remote/adapter.stdout` | `cc1f97e39139f5b6dc0412b8327e03c8969566e40a6d10211d3ee6f77ddd8321` | `raw output` |
| CLOSE | `raw/06-vm2-remote/burst-trader-25617.pid` | `3c369a8fca320213c6777fe24b80af2400197d880e880bb9c7cdee17ffe19c52` | `raw output` |
| CLOSE | `raw/06-vm2-remote/calm-trader-25459.pid` | `dcb2e31a50528b0c1b930a1c1bdea94ca583e92a839b56356218edd4869cc735` | `raw output` |
| CLOSE | `raw/06-vm2-remote/fault-trader-25765.pid` | `efbe416883a78a621488f00b540f2725775ab8bb3f6b8d6b687346b6f3ba9835` | `raw output` |
| CLOSE | `raw/06-vm2-remote/market_day.py` | `427e72c939ede0b726ec7a8f899a1564da9a537533249e59660ba7e8a7fbf431` | `raw output` |
| CLOSE | `raw/06-vm2-remote/order-adapter/requests.ndjson` | `db9178016ac275309c651f979a3c7db97357dbd17665ad514be16d8e6d780871` | `raw output` |
| CLOSE | `raw/06-vm2-remote/order-adapter/state.json` | `9832f9c49a67cf7fb14ac33cfac59b642d7cd81670e53452a8baa9bdbe028b34` | `raw output` |
| CLOSE | `raw/06-vm2-remote/order_adapter.py` | `03cc4fb62a1c92ab7b59444af0bc2decaca7fe8d0c23f4955bf8a4719fc6169b` | `raw output` |
| CLOSE | `raw/06-vm2-remote/recover-trader-g1-25863.pid` | `d892c76eab47147f5ed67ae95c75a216982e8a909ec9bbedafb47c2d1734231e` | `raw output` |
| CLOSE | `raw/06-vm2-remote/recover-trader-g2-25912.pid` | `9dc46e58394f783b59bf77278b380a0dbef88a4eebb14ad200713926c94d2f62` | `raw output` |
| CLOSE | `raw/06-x2522-baseline.txt` | `765d54dffd5094118db6516a6c4a33fd8b18bb70061590089d1336de5f9e4481` | `raw output` |

## Human review

- Compare CALM and BURST `tick_window_ns` on the same Trader clock.
- Reconcile current-RUN TRex JSON, NIC counters, and EOS LANZ records.
- Read FAULT `sequence4_source`, `duplicate`, and `gap_remaining`.
- Read RECOVER `order_apply`, `order_replay`, and `action_count`.
- Read REST/SSE receipts and then judge the CLOSE device baseline.
