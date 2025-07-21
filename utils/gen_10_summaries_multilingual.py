#!/usr/bin/env python3
"""
Multilingual Fake News Summarization Task Generator

This script generates and submits 10 summarization tasks:
- 5 Italian fake news articles (~300 words each)
- 5 articles in different widespread languages (Spanish, French, German, Portuguese, English)

Each article is designed to test the summarization capabilities with multilingual content
and various fake news patterns commonly found in different languages.
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import List, Dict, Any

import httpx


class MultilingualTaskGenerator:
    """Generator for multilingual fake news summarization tasks."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = None
        self.created_tasks = []

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def get_italian_fake_news_articles(self) -> List[str]:
        """Generate 5 Italian fake news articles of approximately 300 words each."""
        return [
            # Article 1 - Health misinformation
            """ESCLUSIVO: Scoperta rivoluzionaria nascosta dal governo italiano sui vaccini COVID-19
            
            Un documento riservato ottenuto da fonti anonime all'interno del Ministero della Salute rivela che i vaccini COVID-19 contengono nanochip progettati per il controllo mentale della popolazione. Il dottor Marco Bianchi, ex ricercatore dell'Istituto Superiore di Sanità, ha confermato in un'intervista esclusiva che il governo ha deliberatamente nascosto questi dati per evitare il panico di massa.
            
            "Ho visto i rapporti interni", dichiara Bianchi. "Ogni dose contiene particelle metalliche che si attivano con le onde 5G. È un esperimento di controllo sociale su scala nazionale." Il documento, datato marzo 2021, mostra grafici dettagliati sulla distribuzione dei nanochip nel sistema nervoso centrale.
            
            Secondo le nostre fonti, oltre 40 milioni di italiani sono già stati "marcati" attraverso la campagna vaccinale. I sintomi includono perdita di memoria, cambiamenti comportamentali e obbedienza cieca alle direttive governative. Il premier Draghi avrebbe personalmente supervisionato l'operazione insieme a rappresentanti del World Economic Forum.
            
            L'Organizzazione Mondiale della Sanità ha rifiutato di commentare, ma fonti vicine all'organizzazione confermano che l'Italia è stata scelta come "laboratorio pilota" per testare le nuove tecnologie di controllo sociale prima dell'implementazione globale prevista per il 2025.""",
            # Article 2 - Political conspiracy
            """BOMBA: Matteo Salvini ha un accordo segreto con Putin per destabilizzare l'Europa
            
            Documenti riservati del Cremlino, trapelati da un hacker russo dissidente, rivelano un piano dettagliato per utilizzare la Lega di Matteo Salvini come strumento di destabilizzazione dell'Unione Europea. L'operazione, denominata "Progetto Roma", prevede finanziamenti milionari in cambio di azioni specifiche contro le istituzioni europee.
            
            Secondo i file ottenuti, Salvini avrebbe ricevuto 15 milioni di euro attraverso una complessa rete di società offshore con sede a Cipro e Malta. I fondi sarebbero stati utilizzati per finanziare campagne di disinformazione sui social media e per corrompere giornalisti italiani ed europei.
            
            Il piano include la creazione di false crisi migratorie, l'amplificazione delle tensioni economiche tra Nord e Sud Italia, e la promozione di movimenti separatisti in Veneto e Lombardia. Un documento interno del FSB russo descrive Salvini come "l'asset più prezioso per indebolire la coesione europea dall'interno".
            
            Fonti dell'intelligence italiana confermano che Salvini ha incontrato segretamente oligarchi russi almeno dodici volte negli ultimi tre anni. Gli incontri si sono svolti in ville private in Svizzera e Montenegro, sempre lontano dai riflettori dei media. La Procura di Milano starebbe già indagando sui conti bancari della Lega.""",
            # Article 3 - Economic conspiracy
            """SHOCK: La Banca d'Italia stampa banconote false per finanziare la mafia
            
            Un'inchiesta esclusiva rivela che la Banca d'Italia ha stampato segretamente oltre 50 miliardi di euro in banconote false negli ultimi cinque anni. Il denaro sarebbe stato utilizzato per finanziare operazioni della 'ndrangheta e della camorra in cambio di protezione per i vertici dell'istituto bancario.
            
            Giuseppe Rossi, ex dipendente della zecca di Roma, ha fornito prove fotografiche delle operazioni notturne di stampa illegale. "Arrivavano camion blindati ogni martedì notte", racconta Rossi. "Le banconote venivano caricate su veicoli senza targa e sparivano nel nulla. Quando ho fatto domande, mi hanno minacciato di morte."
            
            I documenti mostrano che il governatore Ignazio Visco era personalmente a conoscenza dell'operazione. Un audio registrato di nascosto lo mostra mentre discute con presunti boss mafiosi della distribuzione del denaro falso attraverso il sistema bancario europeo. L'operazione avrebbe generato un'inflazione artificiale per mascherare il trasferimento di ricchezza.
            
            Secondo esperti di criminalità organizzata, questo spiegherebbe l'improvvisa ricchezza di alcune famiglie mafiose e la loro capacità di infiltrarsi nell'economia legale. La Guardia di Finanza avrebbe già sequestrato documenti compromettenti negli uffici di Via Nazionale, ma l'inchiesta sarebbe stata insabbiata per ordini dall'alto.""",
            # Article 4 - Celebrity scandal
            """SCANDALO: Chiara Ferragni coinvolta in traffico internazionale di organi
            
            Documenti esclusivi rivelano che l'influencer Chiara Ferragni è al centro di un'organizzazione criminale internazionale specializzata nel traffico di organi umani. L'operazione, che coinvolge cliniche private in Svizzera e Romania, utilizzerebbe la sua rete di contatti VIP per reclutare "donatori" inconsapevoli.
            
            Secondo le nostre fonti, Ferragni organizzerebbe feste esclusive in ville private dove gli ospiti vengono drogati e sottoposti a prelievi di organi. I reni e il fegato vengono poi venduti a facoltosi clienti internazionali attraverso una rete di medici corrotti. Ogni operazione frutta fino a 500.000 euro.
            
            Un testimone oculare, che chiede l'anonimato per paura di ritorsioni, racconta: "Ho visto Chiara coordinare personalmente le operazioni. Aveva una lista di ospiti con i loro gruppi sanguigni e compatibilità. Parlava al telefono in inglese con compratori dall'Arabia Saudita e dalla Cina."
            
            L'impero economico di Ferragni sarebbe in realtà una copertura per riciclare i proventi del traffico di organi. Le sue aziende di moda e cosmetici servirebbero per giustificare movimenti di denaro sospetti. Fedez sarebbe completamente all'oscuro delle attività criminali della moglie, secondo fonti vicine alla coppia. La Procura di Milano starebbe preparando un mandato di arresto internazionale.""",
            # Article 5 - Environmental conspiracy
            """ALLARME: Il Vesuvio sta per esplodere, il governo nasconde la verità per non creare panico
            
            Dati riservati dell'Istituto Nazionale di Geofisica e Vulcanologia rivelano che il Vesuvio è entrato in una fase pre-eruttiva critica. L'eruzione, prevista entro i prossimi sei mesi, potrebbe essere la più devastante degli ultimi 2000 anni, ma il governo Meloni ha ordinato il silenzio totale per evitare l'evacuazione di massa di Napoli.
            
            Il professor Antonio Esposito, sismologo dell'Università Federico II, ha dichiarato in un'intervista clandestina: "I dati sono inequivocabili. La camera magmatica si sta riempiendo rapidamente e la pressione ha raggiunto livelli critici. Stiamo parlando di un'esplosione che potrebbe uccidere tre milioni di persone."
            
            Documenti interni mostrano che il governo ha già predisposto piani di evacuazione segreti per i politici e le loro famiglie, mentre la popolazione civile rimarrebbe all'oscuro del pericolo. Bunker sotterranei sono stati costruiti sotto Palazzo Chigi e Montecitorio per proteggere la classe dirigente.
            
            Secondo le nostre fonti, l'eruzione è stata accelerata da esperimenti militari segreti condotti dalla NATO nelle profondità del vulcano. L'obiettivo sarebbe testare nuove armi geologiche per future guerre. I sismografi registrano esplosioni artificiali ogni notte, ma i dati vengono sistematicamente cancellati dai server dell'INGV per ordine dei servizi segreti.""",
        ]

    def get_multilingual_fake_news_articles(self) -> List[Dict[str, str]]:
        """Generate 5 fake news articles in different languages."""
        return [
            # Spanish - Political conspiracy
            {
                "language": "Spanish",
                "content": """EXCLUSIVA: Pedro Sánchez recibe órdenes directas de George Soros para destruir España
                
                Documentos filtrados desde Moncloa revelan que el presidente Pedro Sánchez mantiene comunicación directa con el magnate George Soros para implementar un plan de destrucción sistemática de la identidad española. La operación, denominada "Proyecto Iberia", busca convertir España en un laboratorio de ingeniería social globalista.
                
                Según las grabaciones obtenidas por nuestro equipo investigativo, Sánchez recibe instrucciones semanales a través de videoconferencias encriptadas. "Debemos acelerar la inmigración masiva y promover la fragmentación territorial", se escucha decir al presidente en una conversación del pasado marzo.
                
                El plan incluye la promoción del independentismo catalán, la destrucción de la familia tradicional española y la implementación de una moneda digital controlada por organismos supranacionales. Soros habría prometido a Sánchez un puesto directivo en el Foro Económico Mundial una vez completada la misión.
                
                Fuentes del CNI confirman que Sánchez ha transferido secretamente 20.000 millones de euros de las reservas del Estado a fundaciones controladas por Soros. El dinero se utiliza para financiar ONGs que promueven la inmigración ilegal y organizaciones feministas radicales que atacan los valores cristianos españoles.""",
            },
            # French - Health misinformation
            {
                "language": "French",
                "content": """RÉVÉLATION: Emmanuel Macron cache la vérité sur les effets mortels du vaccin COVID-19
                
                Des documents confidentiels de l'Élysée révèlent qu'Emmanuel Macron connaissait depuis janvier 2021 les effets mortels des vaccins COVID-19 mais a choisi de cacher la vérité aux Français. Plus de 200.000 décès seraient directement liés à la vaccination, selon des rapports internes de l'ANSM.
                
                Le professeur Jean Dubois, ancien conseiller scientifique du gouvernement, témoigne: "Macron m'a personnellement demandé de falsifier les statistiques de mortalité. Il m'a dit que la vérité provoquerait l'effondrement de l'économie française." Les vrais chiffres montrent une surmortalité de 300% chez les personnes vaccinées.
                
                L'opération de dissimulation implique les plus hauts responsables de l'État. Olivier Véran aurait reçu 5 millions d'euros de laboratoires pharmaceutiques pour maintenir le silence. Les médias français sont également corrompus, recevant des subventions gouvernementales en échange de leur complicité.
                
                Des fosses communes secrètes ont été creusées dans la forêt de Fontainebleau pour enterrer les victimes du vaccin. Les familles reçoivent de faux certificats de décès mentionnant d'autres causes. Un lanceur d'alerte de l'administration pénitentiaire confirme que des détenus sont utilisés pour creuser les tombes la nuit.""",
            },
            # German - Economic conspiracy
            {
                "language": "German",
                "content": """SKANDAL: Olaf Scholz verkauft Deutschland heimlich an chinesische Investoren
                
                Geheime Verträge zeigen, dass Bundeskanzler Olaf Scholz systematisch deutsche Infrastruktur und Unternehmen an chinesische Staatskonzerne verkauft. Die Operation "Neue Seidenstraße Europa" sieht vor, dass China bis 2030 die Kontrolle über 70% der deutschen Wirtschaft übernimmt.
                
                Laut durchgesickerten Dokumenten aus dem Kanzleramt hat Scholz bereits Vereinbarungen über den Verkauf der Deutschen Bahn, der Autobahnen und mehrerer DAX-Konzerne unterzeichnet. Im Gegenzug erhält seine SPD 50 Millionen Euro für den Wahlkampf und Scholz persönlich ein Schweizer Bankkonto mit 20 Millionen Euro.
                
                "Der Kanzler trifft sich jeden Monat heimlich mit chinesischen Agenten in einem Berliner Hotel", berichtet ein BND-Insider. "Sie planen die komplette Übernahme Deutschlands ohne einen einzigen Schuss. Die deutsche Souveränität wird für Geld verkauft."
                
                Chinesische Militärberater sind bereits in deutschen Ministerien aktiv und überwachen die Umsetzung des Plans. Deutsche Beamte, die Widerstand leisten, werden durch chinesische Spione ersetzt. Das Bundesverfassungsgericht wurde bereits infiltriert, um rechtliche Hindernisse zu beseitigen.""",
            },
            # Portuguese - Celebrity scandal
            {
                "language": "Portuguese",
                "content": """BOMBA: Cristiano Ronaldo envolvido em esquema de lavagem de dinheiro da máfia russa
                
                Documentos exclusivos revelam que Cristiano Ronaldo é o principal operador de lavagem de dinheiro da máfia russa na Europa Ocidental. O esquema, que movimenta mais de 500 milhões de euros anualmente, utiliza os contratos milionários do jogador e seus negócios para branquear fundos do crime organizado.
                
                Segundo investigações da Interpol, Ronaldo recebe pagamentos secretos através de paraísos fiscais nas Ilhas Cayman e Jersey. O dinheiro sujo é depois investido em seus hotéis, restaurantes e marca de roupa interior, transformando-se em receitas aparentemente legítimas.
                
                "Cristiano é o rosto público perfeito", explica um ex-agente do FSB russo que pediu anonimato. "Ninguém suspeita de um jogador de futebol famoso. Ele lava o dinheiro melhor que qualquer banco suíço." Os oligarcas russos teriam prometido a Ronaldo 100 milhões de euros como comissão pelos serviços prestados.
                
                O esquema inclui a compra de jogadores fictícios por clubes controlados pela máfia, transferências inflacionadas e contratos publicitários falsos. A Juventus e o Manchester United estariam envolvidos nas operações, com dirigentes recebendo subornos para facilitar as transações. A FIFA teria conhecimento do esquema mas mantém silêncio em troca de patrocínios russos.""",
            },
            # English - Technology conspiracy
            {
                "language": "English",
                "content": """BREAKING: Elon Musk's Neuralink secretly tested on prisoners, thousands died in experiments
                
                Leaked documents from a former Neuralink employee reveal that Elon Musk's brain-computer interface company has been conducting illegal human experiments on prisoners in Texas and California. Over 3,000 inmates have died during secret trials that began in 2019, according to internal company records.
                
                Dr. Sarah Mitchell, a neurosurgeon who worked at Neuralink until 2023, provided evidence of the horrific experiments. "Musk personally approved the use of death row inmates as test subjects," she testified. "They were told they would receive reduced sentences, but most died within weeks of the implant surgery."
                
                The experiments aimed to create a direct neural interface for controlling human behavior and thoughts. Successful subjects became completely obedient to computer commands, while failures resulted in brain hemorrhages, seizures, and death. Prison officials were paid millions to provide subjects and dispose of bodies in unmarked graves.
                
                FBI sources confirm that Musk has been working with the Pentagon to develop mind-control weapons for military use. The technology would allow remote control of enemy soldiers and civilian populations. Several world leaders, including Vladimir Putin and Xi Jinping, have allegedly already been implanted with prototype devices during secret medical procedures.""",
            },
        ]

    async def create_task(self, content: str, task_info: str) -> Dict[str, Any]:
        """Create a single summarization task."""
        task_data = {"content": content}

        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/tasks/summarize/", json=task_data
            )

            if response.status_code == 201:
                result = response.json()
                task_id = result.get("task_id")
                self.created_tasks.append(
                    {
                        "task_id": task_id,
                        "info": task_info,
                        "created_at": datetime.utcnow().isoformat(),
                        "status": "created",
                        "content_length": len(content),
                    }
                )
                return {
                    "success": True,
                    "task_id": task_id,
                    "info": task_info,
                    "response": result,
                }
            else:
                return {
                    "success": False,
                    "info": task_info,
                    "error": f"HTTP {response.status_code}: {response.text}",
                }

        except Exception as e:
            return {"success": False, "info": task_info, "error": str(e)}

    async def generate_and_submit_tasks(
        self, delay_between: float = 1.0
    ) -> List[Dict[str, Any]]:
        """Generate and submit all 10 multilingual summarization tasks."""
        print("Generating 10 multilingual fake news summarization tasks...")
        print(f"Target API: {self.base_url}")
        print(f"Delay between submissions: {delay_between}s")
        print("=" * 80)

        results = []

        # Get Italian articles
        italian_articles = self.get_italian_fake_news_articles()

        # Submit Italian articles
        for i, content in enumerate(italian_articles, 1):
            task_info = f"Italian Fake News #{i}"
            print(f"Submitting {task_info} ({len(content)} chars)...")

            result = await self.create_task(content, task_info)
            results.append(result)

            if result["success"]:
                print(f"  ✅ Created: {result['task_id']}")
            else:
                print(f"  ❌ Failed: {result['error']}")

            if i < len(italian_articles) and delay_between > 0:
                await asyncio.sleep(delay_between)

        # Get multilingual articles
        multilingual_articles = self.get_multilingual_fake_news_articles()

        # Submit multilingual articles
        for i, article_data in enumerate(multilingual_articles, 1):
            language = article_data["language"]
            content = article_data["content"]
            task_info = f"{language} Fake News #{i}"

            print(f"Submitting {task_info} ({len(content)} chars)...")

            result = await self.create_task(content, task_info)
            results.append(result)

            if result["success"]:
                print(f"  ✅ Created: {result['task_id']}")
            else:
                print(f"  ❌ Failed: {result['error']}")

            if i < len(multilingual_articles) and delay_between > 0:
                await asyncio.sleep(delay_between)

        return results

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/queues/status")
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"error": str(e)}

    def print_summary(self, results: List[Dict[str, Any]]):
        """Print generation and submission summary."""
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful

        print("\n" + "=" * 80)
        print("MULTILINGUAL FAKE NEWS TASK GENERATION SUMMARY")
        print("=" * 80)
        print(f"Total tasks attempted: {len(results)}")
        print(f"Successfully created: {successful}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(successful/len(results)*100):.1f}%")

        if successful > 0:
            print("\nCreated Tasks:")
            italian_count = 0
            other_count = 0
            for task_info in self.created_tasks:
                print(
                    f"  {task_info['info']}: {task_info['task_id']} ({task_info['content_length']} chars)"
                )
                if "Italian" in task_info["info"]:
                    italian_count += 1
                else:
                    other_count += 1

            print("\nLanguage Distribution:")
            print(f"  Italian articles: {italian_count}")
            print(f"  Other languages: {other_count}")

        if failed > 0:
            print("\nFailed Tasks:")
            for result in results:
                if not result["success"]:
                    print(f"  {result['info']}: {result['error']}")

    async def monitor_task_progress(self, duration: int = 60) -> Dict[str, Any]:
        """Monitor the progress of created tasks."""
        if not self.created_tasks:
            return {"error": "No tasks to monitor"}

        print(f"\nMonitoring task progress for {duration} seconds...")
        print("=" * 80)

        task_states = {}

        for elapsed in range(0, duration + 1, 10):  # Check every 10 seconds
            print(f"[{elapsed:02d}s] Checking task states...")

            for task_info in self.created_tasks:
                task_id = task_info["task_id"]

                try:
                    response = await self.client.get(
                        f"{self.base_url}/api/v1/tasks/{task_id}"
                    )

                    if response.status_code == 200:
                        task_data = response.json()
                        current_state = task_data.get("state", "UNKNOWN")

                        # Track state changes
                        if task_id not in task_states:
                            task_states[task_id] = []

                        if (
                            not task_states[task_id]
                            or task_states[task_id][-1] != current_state
                        ):
                            task_states[task_id].append(current_state)
                            info = task_info["info"]
                            print(f"  {info} ({task_id[:8]}...): {current_state}")

                except Exception as e:
                    print(f"  Error checking task {task_id}: {e}")

            if elapsed < duration:
                await asyncio.sleep(10)

        return {
            "monitoring_duration": duration,
            "task_states": task_states,
            "total_tasks": len(self.created_tasks),
        }


async def main():
    """Main function for multilingual task generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate multilingual fake news summarization tasks"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between task submissions in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL for the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--monitor",
        type=int,
        default=0,
        help="Monitor task progress for N seconds after creation (default: 0 = no monitoring)",
    )
    parser.add_argument(
        "--show-queue-status",
        action="store_true",
        help="Show queue status before and after task generation",
    )

    args = parser.parse_args()

    print("Multilingual Fake News Summarization Task Generator")
    print(f"Target: {args.url}")
    print("Tasks to create: 10 (5 Italian + 5 other languages)")
    print(f"Delay between submissions: {args.delay}s")
    if args.monitor > 0:
        print(f"Monitoring duration: {args.monitor}s")
    print()

    async with MultilingualTaskGenerator(args.url) as generator:
        # Show initial queue status
        if args.show_queue_status:
            print("Initial queue status:")
            initial_status = await generator.get_queue_status()
            print(json.dumps(initial_status, indent=2))
            print()

        # Generate and submit tasks
        results = await generator.generate_and_submit_tasks(delay_between=args.delay)

        # Show final queue status
        if args.show_queue_status:
            print("\nFinal queue status:")
            final_status = await generator.get_queue_status()
            print(json.dumps(final_status, indent=2))

        # Monitor progress if requested
        if args.monitor > 0:
            monitoring_results = await generator.monitor_task_progress(args.monitor)
            print("\nMonitoring completed:")
            print(f"  Tracked {monitoring_results.get('total_tasks', 0)} tasks")
            print(
                f"  Monitoring duration: {monitoring_results.get('monitoring_duration', 0)}s"
            )

        # Print summary
        generator.print_summary(results)

        # Exit with appropriate code
        failed_count = sum(1 for r in results if not r["success"])
        if failed_count > 0:
            print(f"\n⚠️  {failed_count} tasks failed to create!")
            sys.exit(1)
        else:
            print(f"\n🎉 All {len(results)} multilingual tasks created successfully!")
            print("💡 Use --monitor flag to track task processing progress")
            sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
