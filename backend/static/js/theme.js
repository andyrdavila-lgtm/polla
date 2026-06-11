// Sistema de temas dinámico según países que juegan
class MundialTheme {
    constructor() {
        this.currentTheme = 'default';
        this.init();
    }
    
    init() {
        this.loadThemeFromStorage();
        this.startMatchCheck();
    }
    
    loadThemeFromStorage() {
        const savedTheme = localStorage.getItem('mundial-theme');
        if (savedTheme) {
            this.applyTheme(savedTheme);
        }
    }
    
    async checkCurrentMatches() {
        try {
            const response = await fetch('/api/partidos/hoy');
            const matches = await response.json();
            
            if (matches.length > 0) {
                // Obtener colores de los equipos que juegan hoy
                const colors = this.getColorsFromMatches(matches);
                this.applyDynamicTheme(colors);
            } else {
                this.applyDefaultTheme();
            }
        } catch (error) {
            console.error('Error checking matches:', error);
        }
    }
    
    getColorsFromMatches(matches) {
        const colors = [];
        matches.forEach(match => {
            colors.push(match.local_color, match.visitante_color);
        });
        return colors;
    }
    
    applyDynamicTheme(colors) {
        const primaryColor = colors[0] || '#1a472a';
        const secondaryColor = colors[1] || '#c4a747';
        
        document.documentElement.style.setProperty('--primary-color', primaryColor);
        document.documentElement.style.setProperty('--secondary-color', secondaryColor);
        
        // Aplicar gradiente dinámico al background
        document.body.style.background = `linear-gradient(135deg, ${primaryColor} 0%, ${secondaryColor} 100%)`;
    }
    
    applyDefaultTheme() {
        document.documentElement.style.setProperty('--primary-color', '#1a472a');
        document.documentElement.style.setProperty('--secondary-color', '#c4a747');
        document.body.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
    }
    
    startMatchCheck() {
        // Verificar cada hora
        setInterval(() => this.checkCurrentMatches(), 3600000);
        this.checkCurrentMatches();
    }
    
    applyTheme(themeName) {
        const themes = {
            'argentina': ['#75AADB', '#FFFFFF'],
            'brazil': ['#FFD700', '#228B22'],
            'germany': ['#000000', '#DD0000'],
            'france': ['#0055A4', '#FFFFFF'],
            'default': ['#1a472a', '#c4a747']
        };
        
        const theme = themes[themeName] || themes.default;
        this.applyDynamicTheme(theme);
        localStorage.setItem('mundial-theme', themeName);
    }
}

// Inicializar tema
const mundialTheme = new MundialTheme();