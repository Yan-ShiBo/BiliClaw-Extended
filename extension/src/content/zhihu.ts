/**
 * Zhihu content script entry point.
 * Bundled as dist/content/zhihu.js and injected into zhihu.com pages.
 */

import { startCollector } from "./kernel.js";
import { installZhihuMessageListener } from "./zhihu/task-executor.js";
import { zhihuAdapter } from "../shared/platforms/zhihu.js";

startCollector(zhihuAdapter);
installZhihuMessageListener();
