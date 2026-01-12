/**
 * ArqAI Foundry API Client
 * Handles all API calls to the backend
 */

const API_BASE = 'http://localhost:8000/api/v1';

class ArqAIAPI {
  constructor(baseUrl = API_BASE) {
    this.baseUrl = baseUrl;
    this.tenantId = localStorage.getItem('tenantId') || 'demo-tenant';
    this.userId = localStorage.getItem('userId') || 'demo-user';
  }

  // =========================================
  // Helper Methods
  // =========================================

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    if (config.body && typeof config.body === 'object') {
      config.body = JSON.stringify(config.body);
    }

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API Error [${endpoint}]:`, error);
      throw error;
    }
  }

  get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  }

  post(endpoint, data) {
    return this.request(endpoint, { method: 'POST', body: data });
  }

  put(endpoint, data) {
    return this.request(endpoint, { method: 'PUT', body: data });
  }

  patch(endpoint, data) {
    return this.request(endpoint, { method: 'PATCH', body: data });
  }

  delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }

  // =========================================
  // Health
  // =========================================

  async getHealth() {
    return this.get('/health');
  }

  // =========================================
  // Templates
  // =========================================

  async getTemplates(vertical = null, category = null) {
    let endpoint = '/templates';
    const params = new URLSearchParams();

    if (vertical) params.append('vertical', vertical);
    if (category) params.append('category', category);

    if (params.toString()) {
      endpoint += `?${params.toString()}`;
    }

    return this.get(endpoint);
  }

  async getTemplate(templateId) {
    return this.get(`/templates/${templateId}`);
  }

  async searchTemplates(query) {
    return this.get(`/templates/search?query=${encodeURIComponent(query)}`);
  }

  // =========================================
  // Builder Sessions
  // =========================================

  async createSession() {
    return this.post('/builder/sessions', {
      tenant_id: this.tenantId,
      user_id: this.userId,
    });
  }

  async getSession(sessionId) {
    return this.get(`/builder/sessions/${sessionId}`);
  }

  async selectTemplate(sessionId, templateId) {
    return this.post(`/builder/sessions/${sessionId}/template`, {
      template_id: templateId,
    });
  }

  async updateAgentName(sessionId, name, description = '') {
    return this.put(`/builder/sessions/${sessionId}/agent`, {
      name,
      description,
    });
  }

  async updateParameters(sessionId, parameters) {
    return this.put(`/builder/sessions/${sessionId}/parameters`, {
      parameters,
    });
  }

  async updateCapabilities(sessionId, enabled, disabled) {
    return this.put(`/builder/sessions/${sessionId}/capabilities`, {
      enabled_capabilities: enabled,
      disabled_capabilities: disabled,
    });
  }

  async updateIntegrations(sessionId, integrations) {
    return this.put(`/builder/sessions/${sessionId}/integrations`, {
      integrations,
    });
  }

  async validateSession(sessionId) {
    return this.post(`/builder/sessions/${sessionId}/validate`, {});
  }

  async deployAgent(sessionId, agentName, environment = 'production') {
    return this.post(`/builder/sessions/${sessionId}/deploy`, {
      agent_name: agentName,
      environment,
    });
  }

  // =========================================
  // Agents
  // =========================================

  async getAgents(status = null) {
    let endpoint = `/agents?tenant_id=${this.tenantId}`;
    if (status) {
      endpoint += `&status=${status}`;
    }
    return this.get(endpoint);
  }

  async getAgent(agentId) {
    return this.get(`/agents/${agentId}`);
  }

  async updateAgentStatus(agentId, status) {
    return this.patch(`/agents/${agentId}/status?status=${status}`, {});
  }

  async deleteAgent(agentId) {
    return this.delete(`/agents/${agentId}`);
  }

  // =========================================
  // Workspaces
  // =========================================

  async getWorkspaces() {
    return this.get(`/workspaces?tenant_id=${this.tenantId}`);
  }

  async createWorkspace(name, description = '') {
    return this.post('/workspaces', {
      tenant_id: this.tenantId,
      name,
      description,
      owner_id: this.userId,
    });
  }

  async getWorkspaceSummary(workspaceId) {
    return this.get(`/workspaces/${workspaceId}/summary`);
  }

  // =========================================
  // Integrations
  // =========================================

  async getIntegrationTypes() {
    return this.get('/integrations/types');
  }

  async getIntegrations() {
    return this.get(`/integrations?tenant_id=${this.tenantId}`);
  }

  async testIntegration(type, config) {
    return this.post('/integrations/test', { type, config });
  }

  // =========================================
  // LLM
  // =========================================

  async getLLMProviders() {
    return this.get('/llm/providers');
  }

  async getRegisteredLLMs() {
    return this.get(`/llm?tenant_id=${this.tenantId}`);
  }

  async registerLLM(provider, name, config) {
    return this.post('/llm', {
      tenant_id: this.tenantId,
      provider,
      name,
      config,
    });
  }

  async testLLM(provider, config) {
    return this.post('/llm/test', { provider, config });
  }

  // =========================================
  // Evidence
  // =========================================

  async getEvidence(limit = 50) {
    return this.get(`/evidence?tenant_id=${this.tenantId}&limit=${limit}`);
  }

  async verifyEvidence(evidenceId) {
    return this.get(`/evidence/${evidenceId}/verify`);
  }
}

// Create global instance
const api = new ArqAIAPI();

// =========================================
// Utility Functions
// =========================================

function showLoading(show = true) {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) {
    overlay.style.display = show ? 'flex' : 'none';
  }
}

function showAlert(message, type = 'info') {
  const container = document.getElementById('alert-container');
  if (!container) return;

  const alert = document.createElement('div');
  alert.className = `alert alert-${type}`;
  alert.innerHTML = `
    <span>${message}</span>
    <button onclick="this.parentElement.remove()" style="background:none;border:none;color:inherit;cursor:pointer;margin-left:auto;">&times;</button>
  `;

  container.appendChild(alert);

  setTimeout(() => alert.remove(), 5000);
}

function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getVerticalIcon(vertical) {
  const icons = {
    finance: '💰',
    healthcare: '🏥',
    energy: '⚡',
    government: '🏛️',
  };
  return icons[vertical] || '📦';
}

function getVerticalColor(vertical) {
  const colors = {
    finance: 'finance',
    healthcare: 'healthcare',
    energy: 'energy',
    government: 'government',
  };
  return colors[vertical] || '';
}

function getCategoryIcon(category) {
  const icons = {
    cost_optimization: '💵',
    compliance: '✅',
    security: '🔒',
    operations: '⚙️',
    data_management: '📊',
    workflow: '🔄',
    analytics: '📈',
  };
  return icons[category] || '📦';
}

// Store session data
const sessionStore = {
  currentSession: null,
  currentTemplate: null,

  save() {
    localStorage.setItem('builderSession', JSON.stringify({
      currentSession: this.currentSession,
      currentTemplate: this.currentTemplate,
    }));
  },

  load() {
    const data = localStorage.getItem('builderSession');
    if (data) {
      const parsed = JSON.parse(data);
      this.currentSession = parsed.currentSession;
      this.currentTemplate = parsed.currentTemplate;
    }
  },

  clear() {
    this.currentSession = null;
    this.currentTemplate = null;
    localStorage.removeItem('builderSession');
  },
};
