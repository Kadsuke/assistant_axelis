"""
Configuration et orchestration CrewAI
"""
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from crewai import Agent, Task, Crew
from crewai_tools import tool
import structlog

logger = structlog.get_logger()

class CorisCrewManager:
    def __init__(self):
        self.agents_config = self._load_agents_config()
        self.tasks_config = self._load_tasks_config()
        self.agents = {}
        self.tasks = {}
    
    def _load_agents_config(self) -> Dict:
        """Charge la configuration des agents"""
        configs = {}
        
        # Charger les agents core
        core_path = Path("src/agents/core")
        for config_file in core_path.glob("*.yaml"):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                configs.update(config.get('agents', {}))
        
        # Charger les agents d'applications
        apps_path = Path("src/agents/applications")
        for app_dir in apps_path.iterdir():
            if app_dir.is_dir():
                for config_file in app_dir.glob("*.yaml"):
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                        configs.update(config.get('agents', {}))
        
        return configs
    
    def _load_tasks_config(self) -> Dict:
        """Charge la configuration des tâches"""
        tasks_path = Path("src/agents/config/tasks.yaml")
        if tasks_path.exists():
            with open(tasks_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('tasks', {})
        return {}
    
    def create_agent(self, agent_name: str, filiale_id: str, available_tools: List = None) -> Agent:
        """Crée un agent CrewAI depuis la configuration"""
        if agent_name not in self.agents_config:
            raise ValueError(f"Agent {agent_name} not found in configuration")
        
        config = self.agents_config[agent_name]
        
        # Vérifier les permissions de pack si nécessaire
        required_pack = config.get('required_pack')
        if required_pack:
            from core.packs.manager import MultiAppPackManager
            pack_manager = MultiAppPackManager()
            # Logique de vérification des permissions
        
        agent = Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            max_iter=config.get('max_iter', 3),
            memory=config.get('memory', True),
            verbose=config.get('verbose', False),
            allow_delegation=config.get('allow_delegation', False),
            tools=available_tools or []
        )
        
        self.agents[agent_name] = agent
        logger.info(f"Agent created: {agent_name}")
        
        return agent
    
    def create_task(self, task_name: str, agent: Agent, context: List[Task] = None) -> Task:
        """Crée une tâche CrewAI depuis la configuration"""
        if task_name not in self.tasks_config:
            raise ValueError(f"Task {task_name} not found in configuration")
        
        config = self.tasks_config[task_name]
        
        task = Task(
            description=config['description'],
            expected_output=config['expected_output'],
            agent=agent,
            context=context or []
        )
        
        self.tasks[task_name] = task
        logger.info(f"Task created: {task_name}")
        
        return task
    
    def create_coris_money_crew(self, filiale_id: str, user_query: str) -> Crew:
        """Crée un crew spécialisé pour Coris Money"""
        
        # Import des tools disponibles
        from tools.core.nlp_tools import classify_intent, detect_language
        from tools.applications.coris_money.banking_apis import coris_faq_search
        
        # Créer les agents selon le contexte
        customer_service = self.create_agent("core_customer_service", filiale_id)
        banking_assistant = self.create_agent("coris_banking_assistant", filiale_id)
        
        # Créer les tâches
        welcome_task = self.create_task("welcome_and_classify", customer_service)
        faq_task = self.create_task("handle_faq_query", banking_assistant, context=[welcome_task])
        
        # Créer le crew
        crew = Crew(
            agents=[customer_service, banking_assistant],
            tasks=[welcome_task, faq_task],
            verbose=True,
            memory=True
        )
        
        return crew
    
    async def process_user_query(self, filiale_id: str, application: str, 
                                user_id: str, query: str) -> Dict:
        """Traite une requête utilisateur avec CrewAI"""
        
        try:
            # Créer le crew approprié selon l'application
            if application == "coris_money":
                crew = self.create_coris_money_crew(filiale_id, query)
            else:
                raise ValueError(f"Application {application} not supported")
            
            # Exécuter le crew
            result = crew.kickoff({
                "user_query": query,
                "user_id": user_id,
                "filiale_id": filiale_id
            })
            
            logger.info("Crew execution completed", 
                       filiale_id=filiale_id,
                       application=application,
                       user_id=user_id)
            
            return {
                "success": True,
                "result": result,
                "crew_agents": [agent.role for agent in crew.agents],
                "tasks_executed": len(crew.tasks)
            }
            
        except Exception as e:
            logger.error("Crew execution failed", 
                        error=str(e),
                        filiale_id=filiale_id,
                        application=application)
            
            return {
                "success": False,
                "error": str(e),
                "fallback_message": "Désolé, une erreur s'est produite. Un agent humain va vous contacter."
            }