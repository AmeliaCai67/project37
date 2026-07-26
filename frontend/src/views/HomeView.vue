<template>
  <div class="home-container">
    <!-- 全局拖拽上传区 -->
    <GlobalDropZone />

    <!-- 顶部导航 -->
    <header class="top-header">
      <div class="header-inner">
      <div class="brand"></div>

      <div class="header-right">
        <nav class="nav-links">
          <RouterLink to="/" class="nav-link" :class="{ active: $route.path === '/' }">对话</RouterLink>
          <RouterLink to="/files" class="nav-link" :class="{ active: $route.path === '/files' }">文件</RouterLink>
          <RouterLink to="/workspace" class="nav-link nav-tooltip" :class="{ active: $route.path === '/workspace' }">
            我的数据空间
            <span class="tooltip-text">挂载本地文件夹，让 37 直接读取你的数据</span>
          </RouterLink>
        </nav>
        <span class="user-name">{{ userStore.user?.username }}</span>
        <button class="logout-btn" @click="logout" title="退出登录">退出</button>
      </div>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { useRouter, RouterLink, RouterView } from 'vue-router'
import { useUserStore } from '@/stores/user'
import GlobalDropZone from '@/components/GlobalDropZone.vue'

const router = useRouter()
const userStore = useUserStore()

function logout() {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.top-header {
  height: 56px;
  background: var(--parchment-light);
  border-bottom: 0.5px solid #E0D0B0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 28px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  max-width: 1200px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.nav-links {
  display: flex;
  gap: 4px;
}

.nav-link {
  padding: 5px 12px;
  border-radius: 4px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font-sans);
  transition: all var(--duration-fast) ease;
}

.nav-link:hover {
  color: var(--ink-brown);
  background: var(--parchment-dark);
}

.nav-link.active {
  color: var(--ink-brown);
  background: var(--parchment-dark);
}

/* 纸墨风 tooltip：hover 导航项时浮现 */
.nav-tooltip {
  position: relative;
}

.tooltip-text {
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  white-space: nowrap;
  background: var(--parchment-light);
  border: 0.5px solid #E0D0B0;
  color: var(--ink-brown);
  font-size: 11px;
  font-weight: 400;
  padding: 4px 10px;
  box-shadow: 2px 3px 6px rgba(79, 60, 43, 0.08);
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--duration-fast) ease;
  z-index: 110;
}

.nav-tooltip:hover .tooltip-text {
  opacity: 1;
}

.user-name {
  font-size: 13px;
  color: var(--text-secondary);
}

.logout-btn {
  padding: 4px 10px;
  font-size: 12px;
  color: var(--text-tertiary);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  cursor: pointer;
  transition: all var(--duration-fast) ease;
}

.logout-btn:hover {
  color: var(--ink-brown);
  border-color: var(--ink-brown-light);
}

.main-content {
  flex: 1;
  overflow: hidden;
}

@media (max-width: 640px) {
  .top-header { padding: 0 16px; }
  .nav-links { gap: 0; }
  .user-name { display: none; }
}
</style>
