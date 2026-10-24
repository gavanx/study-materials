// 腾讯云开发（CloudBase）同步配置
// 留空则只在本机保存（当前默认行为）；填好下面两项即可开启多设备同步。
// 配置步骤见 CLOUD-SYNC.md
window.QUIZ_CONFIG = {
  cloudbase: {
    envId: '',        // 形如 family-quiz-1a2b3c
    accessKey: '',    // 控制台「环境 > API Key」里的 publishable key
    region: 'ap-shanghai',
    collection: 'quiz_events'
  }
};
