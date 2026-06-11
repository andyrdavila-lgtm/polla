class API {
    constructor() {
        this.baseURL = 'http://localhost:5000/api';
        this.token = localStorage.getItem('token');
    }
    
    async request(endpoint, method = 'GET', data = null) {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        const config = {
            method,
            headers
        };
        
        if (data) {
            config.body = JSON.stringify(data);
        }
        
        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, config);
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.message || 'Error en la petición');
            }
            
            return result;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }
    
    // Autenticación
    async login(username, password) {
        const result = await this.request('/login', 'POST', { username, password });
        if (result.token) {
            this.token = result.token;
            localStorage.setItem('token', result.token);
            localStorage.setItem('user', JSON.stringify(result.user));
        }
        return result;
    }
    
    async register(userData) {
        return await this.request('/register', 'POST', userData);
    }
    
    logout() {
        this.token = null;
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login.html';
    }
    
    // Usuarios
    async getPerfil(usuarioId) {
        return await this.request(`/perfil/${usuarioId}`);
    }
    
    async getTablaPosiciones() {
        return await this.request('/tabla-posiciones');
    }
    
    async getTop5() {
        return await this.request('/top-5');
    }
    
    // Partidos y pronósticos
    async getPartidos(fase = null) {
        const url = fase ? `/partidos?fase=${fase}` : '/partidos';
        return await this.request(url);
    }
    
    async savePronosticoPartido(partidoId, golesLocal, golesVisitante) {
        return await this.request('/pronostico-partido', 'POST', {
            partido_id: partidoId,
            goles_local: golesLocal,
            goles_visitante: golesVisitante
        });
    }
    
    async savePronosticoEspecial(pronosticos) {
        return await this.request('/pronostico-especial', 'POST', pronosticos);
    }
    
    async getHistorialPartidos() {
        return await this.request('/historial-partidos');
    }
    
    // Admin
    async actualizarResultado(partidoId, golesLocal, golesVisitante) {
        return await this.request('/actualizar-resultado', 'PUT', {
            partido_id: partidoId,
            goles_local: golesLocal,
            goles_visitante: golesVisitante
        });
    }
}

const api = new API();