import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/setup',
    name: 'Setup',
    component: () => import('@/views/SetupView.vue'),
    meta: { public: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomeView.vue'),
    children: [
      {
        path: '',
        name: 'Chat',
        component: () => import('@/views/ChatView.vue')
      },
      {
        path: 'files',
        name: 'Files',
        component: () => import('@/views/FilesView.vue')
      },
      {
        path: 'workspace',
        name: 'Workspace',
        component: () => import('@/views/WorkspaceView.vue')
      },
      {
        path: 'conversation/:id',
        name: 'Conversation',
        component: () => import('@/views/ChatView.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
// 注意：必须先 await initAuth()——user 是异步加载的，同步判断会在刷新/重开页面时
// 误判为未登录并踢到 /login。personal 模式下 initAuth 内部 autoLogin 成功，用户永远
// 不会看到登录页；team 模式 autoLogin 403，才会落到 /login。
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()
  await userStore.initAuth()
  
  if (!to.meta.public && !userStore.isLoggedIn) {
    next('/login')
  } else if (to.path === '/login' && userStore.isLoggedIn) {
    next('/')
  } else {
    next()
  }
})

export default router
