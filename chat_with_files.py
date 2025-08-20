import os
import streamlit as st
from typing import List, Dict, Any, Optional, Tuple
import json
import logging
from datetime import datetime
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery, VectorQuery
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import time
import re
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from auth_utils import get_search_credential,get_openai_client,get_content_safety_client

load_dotenv()

# Environment variables
OPENAI_ENDPOINT_URL = os.getenv("OPENAI_ENDPOINT_URL")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
SEARCH_SERVICE_ENDPOINT = os.getenv("SEARCH_SERVICE_ENDPOINT")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# Configure logging
logger = logging.getLogger(__name__)

class QueryPlanner:
    """Intelligent query planning agent for complex questions"""
    
    def __init__(self, openai_client: AzureOpenAI, deployment_name: str):
        self.openai_client = openai_client
        self.deployment_name = deployment_name
    
    def analyze_query(self, query: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Analyze query complexity and plan retrieval strategy"""
        
        analysis_prompt = f"""
        You are an intelligent query analyzer for a RAG system. Analyze the following query and provide a structured response.
        
        Query: "{query}"
        
        Conversation History: {json.dumps(conversation_history or [], indent=2)}
        
        Analyze the query and respond with a JSON object containing:
        1. "complexity": "simple" | "moderate" | "complex"
        2. "query_type": "factual" | "analytical" | "comparative" | "procedural" | "definitional"
        3. "requires_decomposition": true | false
        4. "subqueries": [] (if decomposition needed, list 2-3 focused subqueries)
        5. "search_strategy": "keyword" | "semantic" | "hybrid"
        6. "expected_sources": number of sources likely needed
        7. "context_dependent": true | false (if it depends on conversation history)
        
        Focus on understanding the user's intent and information needs.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": analysis_prompt}],
                max_tokens=1000,
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            # Extract JSON from the response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback analysis
                return {
                    "complexity": "moderate",
                    "query_type": "factual",
                    "requires_decomposition": False,
                    "subqueries": [],
                    "search_strategy": "hybrid",
                    "expected_sources": 3,
                    "context_dependent": False
                }
                
        except Exception as e:
            logger.error(f"Error in query analysis: {str(e)}")
            return {
                "complexity": "moderate",
                "query_type": "factual", 
                "requires_decomposition": False,
                "subqueries": [],
                "search_strategy": "hybrid",
                "expected_sources": 3,
                "context_dependent": False
            }

class HybridSearchAgent:
    """Advanced hybrid search agent with semantic ranking"""
    
    def __init__(self, search_client: SearchClient, openai_client: AzureOpenAI):
        self.search_client = search_client
        self.openai_client = openai_client
        
    def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for the query"""
        try:
            response = self.openai_client.embeddings.create(
                input=query,
                model=EMBEDDING_MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating query embedding: {str(e)}")
            return [0.0] * 3072  # Return zero vector as fallback
    
    def execute_hybrid_search(self, query: str, k: int = 10, use_semantic: bool = True) -> List[Dict]:
        """Execute hybrid search with semantic ranking"""
        try:
            # Generate query embedding
            query_vector = self.generate_query_embedding(query)
            
            # Create vector query
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=k,
                fields="content_vector",
                exhaustive=False
            )
            
            # Build search parameters
            search_params = {
                "search_text": query,
                "vector_queries": [vector_query],
                "select": ["id", "content", "page_number", "file_name", "chunk_id"],
                "top": k,
                "include_total_count": True
            }
            
            # Add semantic ranking if enabled
            if use_semantic:
                search_params.update({
                    "query_type": "semantic",
                    "semantic_configuration_name": "semantic_config",
                    "query_caption": "extractive",
                    "query_answer": "extractive"
                })
            
            # Execute search
            results = self.search_client.search(**search_params)
            
            # Process results
            search_results = []
            for result in results:
                doc_result = {
                    "id": result.get("id"),
                    "content": result.get("content"),
                    "page_number": result.get("page_number"),
                    "file_name": result.get("file_name"),
                    "chunk_id": result.get("chunk_id"),
                    "search_score": result.get("@search.score", 0),
                    "reranker_score": result.get("@search.reranker_score"),
                    "captions": result.get("@search.captions", []),
                    "highlights": result.get("@search.highlights", {})
                }
                search_results.append(doc_result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {str(e)}")
            return []

class ContextValidator:
    """Validates retrieved context and determines if re-retrieval is needed"""
    
    def __init__(self, openai_client: AzureOpenAI, deployment_name: str):
        self.openai_client = openai_client
        self.deployment_name = deployment_name
    
    def validate_context(self, query: str, retrieved_docs: List[Dict]) -> Dict[str, Any]:
        """Validate if retrieved context can answer the query"""
        
        if not retrieved_docs:
            return {
                "is_sufficient": False,
                "confidence": 0.0,
                "reason": "No documents retrieved",
                "suggestions": ["Try different search terms", "Check document availability"]
            }
        
        # Prepare context for validation
        context_text = "\n\n".join([doc.get("content", "") for doc in retrieved_docs[:5]])
        
        validation_prompt = f"""
        As a context validator, determine if the provided context contains sufficient information to answer the user's question.
        
        Question: "{query}"
        
        Context:
        {context_text}
        
        Analyze the context and respond with a JSON object:
        {{
            "is_sufficient": true/false,
            "confidence": 0.0-1.0,
            "reason": "explanation of why context is/isn't sufficient",
            "missing_aspects": ["list", "of", "missing", "information"],
            "suggestions": ["improvement", "suggestions"]
        }}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": validation_prompt}],
                max_tokens=500,
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {
                    "is_sufficient": len(retrieved_docs) > 0,
                    "confidence": 0.7 if retrieved_docs else 0.0,
                    "reason": "Basic validation based on document count",
                    "missing_aspects": [],
                    "suggestions": []
                }
                
        except Exception as e:
            logger.error(f"Error in context validation: {str(e)}")
            return {
                "is_sufficient": len(retrieved_docs) > 0,
                "confidence": 0.5,
                "reason": "Validation failed, assuming moderate sufficiency",
                "missing_aspects": [],
                "suggestions": []
            }

class CleanAnswerAgent:
    """Clean answer generation focused only on the answer content"""
    
    def __init__(self, openai_client: AzureOpenAI, deployment_name: str):
        self.openai_client = openai_client
        self.deployment_name = deployment_name
    
    def generate_answer(self, query: str, context_docs: List[Dict], 
                       conversation_history: List[Dict] = None,
                       query_analysis: Dict = None) -> Dict[str, Any]:
        """Generate clean, focused answer without extra sections"""
        
        # Prepare context
        context_parts = []
        for i, doc in enumerate(context_docs[:10], 1):
            content = doc.get("content", "")
            file_name = doc.get("file_name", "Unknown")
            page_num = doc.get("page_number", "Unknown")
            
            context_parts.append(f"[Source {i}] From {file_name}, Page {page_num}:\n{content}")
        
        context_text = "\n\n".join(context_parts)
        
        # Prepare conversation history
        history_text = ""
        if conversation_history:
            recent_history = conversation_history[-3:]  # Last 3 exchanges
            history_parts = []
            for exchange in recent_history:
                history_parts.append(f"Q: {exchange.get('question', '')}")
                history_parts.append(f"A: {exchange.get('answer', '')}")
            history_text = "\n".join(history_parts)
        
        # Generate system prompt for clean answers
        system_prompt = f"""
        You are a professional document analyst providing direct, focused answers to business queries.
        
        Instructions:
        1. Provide a clear, direct answer to the question asked
        2. Use specific data, numbers, and facts from the provided context
        3. Cite sources with [Source X] notation when referencing specific information
        4. Keep the response focused and concise
        5. DO NOT include separate sections for "Market Trends", "Findings", or "Conclusion"
        6. DO NOT add executive summaries or additional commentary
        7. Simply answer the question directly based on the available information
        
        If information is incomplete, state what's missing clearly within your answer.
        """
        
        user_prompt = f"""
        Question: {query}
        
        {f"Previous Conversation: {history_text}" if history_text else ""}
        
        Available Context:
        {context_text}
        
        Please provide a direct answer to the question based on the available information.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1500,
                temperature=0.2
            )
            
            answer = response.choices[0].message.content
            
            # Get most relevant page numbers
            most_relevant_pages = self.get_most_relevant_pages(context_docs[:3])
            
            return {
                "answer": answer,
                "most_relevant_pages": most_relevant_pages,
                "confidence": min(len(context_docs) / 5.0, 1.0),
                "sources_used": len(context_docs),
                "reasoning_type": query_analysis.get("query_type", "factual") if query_analysis else "factual"
            }
            
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            return {
                "answer": "I apologize, but I encountered an error while processing your question. Please try again.",
                "most_relevant_pages": [],
                "confidence": 0.0,
                "sources_used": 0,
                "reasoning_type": "error"
            }
    
    def get_most_relevant_pages(self, top_docs: List[Dict]) -> List[Dict]:
        """Get the most relevant page numbers from top documents"""
        relevant_pages = []
        
        for doc in top_docs:
            page_info = {
                "file_name": doc.get("file_name", "Unknown"),
                "page_number": doc.get("page_number", "Unknown"),
                "relevance_score": doc.get("search_score", 0)
            }
            relevant_pages.append(page_info)
        
        return relevant_pages

class AgenticRAGOrchestrator:
    """Main orchestrator for the agentic RAG system"""
    
    def __init__(self, search_client: SearchClient, openai_client: AzureOpenAI, deployment_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.deployment_name = deployment_name
        self.safety_client = get_content_safety_client()
        
        # Initialize agents
        self.query_planner = QueryPlanner(openai_client, deployment_name)
        self.search_agent = HybridSearchAgent(search_client, openai_client)
        self.context_validator = ContextValidator(openai_client, deployment_name)
        self.answer_agent = CleanAnswerAgent(openai_client, deployment_name)
    
    def process_query(self, query: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Process query through the complete agentic pipeline"""
        
        start_time = time.time()

        # Optional input safety gate
        if self.safety_client:
            try:
                from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
                analysis = self.safety_client.analyze_text(
                    AnalyzeTextOptions(text=query, categories=[
                        TextCategory.HATE, TextCategory.SEXUAL, TextCategory.VIOLENCE, TextCategory.HARASSMENT
                    ])
                )
                # Simple thresholding: block if any severity >= 2
                if any(cat.severity and cat.severity >= 2 for cat in analysis.categories_analysis):
                    return {
                        "query": query,
                        "answer": "I cannot process this request due to content safety policies.",
                        "query_analysis": {},
                        "search_results": [],
                        "context_validation": {"is_sufficient": False, "reason": "Blocked by content safety"},
                        "most_relevant_pages": [],
                        "confidence": 0.0,
                        "sources_used": 0,
                        "processing_time": time.time() - start_time,
                        "timestamp": datetime.now().isoformat()
                    }
            except Exception as e:
                logger.warning(f"Content safety input check failed: {e}")
        
        # Step 1: Query Planning
        query_analysis = self.query_planner.analyze_query(query, conversation_history)
        
        # Step 2: Initial Search
        if query_analysis.get("requires_decomposition", False):
            # Handle complex queries with decomposition
            subqueries = query_analysis.get("subqueries", [query])
            all_results = []
            
            for subquery in subqueries:
                results = self.search_agent.execute_hybrid_search(subquery, k=5)
                all_results.extend(results)
            
            # Remove duplicates and sort by relevance
            unique_results = {}
            for result in all_results:
                doc_id = result.get("id")
                if doc_id not in unique_results or result.get("search_score", 0) > unique_results[doc_id].get("search_score", 0):
                    unique_results[doc_id] = result
            
            search_results = list(unique_results.values())
            search_results.sort(key=lambda x: x.get("search_score", 0), reverse=True)
            
        else:
            # Simple query processing
            search_results = self.search_agent.execute_hybrid_search(query, k=10)
        
        # Step 3: Context Validation
        context_validation = self.context_validator.validate_context(query, search_results)
        
        # Step 4: Answer Generation
        answer_result = self.answer_agent.generate_answer(
            query, search_results, conversation_history, query_analysis
        )

        # Optional groundedness check using a deterministic critic
        try:
            context_text = "\n\n".join([doc.get("content", "") for doc in search_results[:6]])
            critic_prompt = (
                "You are a strict verifier. Determine if the ANSWER is fully supported by the CONTEXT quotes.\n"
                "Respond with exactly one word: SUPPORTED or UNSUPPORTED.\n\nCONTEXT:\n" + context_text + "\n\nANSWER:\n" + answer_result["answer"]
            )
            critic = self.openai_client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": critic_prompt}],
                temperature=0.0,
                max_tokens=3
            )
            grounded = "SUPPORTED" in (critic.choices[0].message.content or "")
            if not grounded:
                answer_result["answer"] = (
                    "I don't have enough evidence in the indexed documents to confidently answer this. "
                    "Please rephrase or provide more context."
                )
                answer_result["confidence"] = 0.0
        except Exception as e:
            logger.warning(f"Groundedness check failed: {e}")

        # Optional output safety gate
        if self.safety_client:
            try:
                from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
                out_analysis = self.safety_client.analyze_text(
                    AnalyzeTextOptions(text=answer_result["answer"], categories=[
                        TextCategory.HATE, TextCategory.SEXUAL, TextCategory.VIOLENCE, TextCategory.HARASSMENT
                    ])
                )
                if any(cat.severity and cat.severity >= 2 for cat in out_analysis.categories_analysis):
                    answer_result["answer"] = (
                        "I cannot return the generated content due to content safety policies."
                    )
                    answer_result["confidence"] = 0.0
            except Exception as e:
                logger.warning(f"Content safety output check failed: {e}")
        
        # Step 5: Compile final response
        processing_time = time.time() - start_time
        
        return {
            "query": query,
            "query_analysis": query_analysis,
            "search_results": search_results,
            "context_validation": context_validation,
            "answer": answer_result["answer"],
            "most_relevant_pages": answer_result["most_relevant_pages"],
            "confidence": answer_result["confidence"],
            "sources_used": answer_result["sources_used"],
            "processing_time": processing_time,
            "timestamp": datetime.now().isoformat()
        }

def main():
    st.title("🤖 Enhanced Agentic RAG Chat")
    st.markdown("### Hybrid Search + Semantic Ranking + Multi-Agent Intelligence")
    
    # Check if index exists
    index_name = st.session_state.get('index_name')
    if not index_name:
        st.warning("⚠️ Please run the data pipeline first to create a search index.")
        return
    
    # Initialize clients
    try:
        #credential = DefaultAzureCredential()
        credential = get_search_credential()

        # openai_client = AzureOpenAI(
        #     azure_ad_token_provider=lambda: credential
        #         .get_token("https://cognitiveservices.azure.com/.default").token,
        #     azure_endpoint=OPENAI_ENDPOINT_URL,
        #     api_version="2024-02-01"
        # )

        openai_client = get_openai_client()
        
        search_client = SearchClient(
            endpoint=SEARCH_SERVICE_ENDPOINT,
            index_name=index_name,
            credential=credential
        )
        
        # Initialize agentic orchestrator
        orchestrator = AgenticRAGOrchestrator(search_client, openai_client, DEPLOYMENT_NAME)
        
    except Exception as e:
        st.error(f"❌ Error initializing clients: {str(e)}")
        return
    
    # Initialize chat history
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []
    
    if "query_logs" not in st.session_state:
        st.session_state.query_logs = []
    
    # Display chat history
    if st.session_state.conversation_history:
        st.markdown("### 💬 Conversation History")
        
        for i, exchange in enumerate(st.session_state.conversation_history[-3:]):  # Show last 3
            with st.expander(f"Q{i+1}: {exchange['question'][:100]}..."):
                st.markdown(f"**Question:** {exchange['question']}")
                st.markdown(f"**Answer:** {exchange['answer']}")
                
                if exchange.get('most_relevant_pages'):
                    st.markdown("**Most Relevant Pages:**")
                    for page in exchange['most_relevant_pages']:
                        st.markdown(f"- {page.get('file_name', 'Unknown')} (Page {page.get('page_number', 'N/A')})")
    
    # Query input section
    st.markdown("### 🔍 Ask Your Question")
    
    # Column 1: Query input and search button
    col1, col2 = st.columns([3, 1])
    
    with col1:
        user_query = st.text_input(
            "Enter your question:",
            placeholder="e.g., What are the key financial metrics for Q3 2024?",
            key="user_query"
        )
        
        # Query type display
        if user_query.strip():
            try:
                # Quick query analysis for display
                temp_analysis = orchestrator.query_planner.analyze_query(user_query)
                query_type = temp_analysis.get("query_type", "factual")
                complexity = temp_analysis.get("complexity", "moderate")
                
                st.info(f"📊 Query Type: **{query_type.title()}** | Complexity: **{complexity.title()}**")
            except:
                pass
        
        # Search button below query type
        search_button = st.button("🚀 Search", type="primary", use_container_width=True)
    
    with col2:
        # Advanced options
        st.markdown("**Options:**")
        max_sources = st.slider("Max sources", 5, 15, 8)
        confidence_threshold = st.slider("Confidence", 0.0, 1.0, 0.6)
    
    # Process query
    if search_button and user_query.strip():
        with st.spinner("🧠 Processing your question..."):
            try:
                # Process query through agentic pipeline
                result = orchestrator.process_query(
                    user_query,
                    st.session_state.conversation_history
                )
                
                # Display results
                st.markdown("### 📄 Answer")
                
                # Main answer (clean, no extra sections)
                answer = result.get("answer", "No answer generated")
                st.markdown(answer)
                
                # Most relevant pages section
                most_relevant_pages = result.get("most_relevant_pages", [])
                print(most_relevant_pages)
                if most_relevant_pages:
                    st.markdown("### 📚 Most Relevant Pages")
                    
                    for i, page in enumerate(most_relevant_pages, 1):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.markdown(f"**{i}. {page.get('file_name', 'Unknown')}**")
                        with col2:
                            st.markdown(f"Page {page.get('page_number', 'N/A')}")
                        with col3:
                            st.markdown(f"Score: {page.get('relevance_score', 0):.3f}")
                
                # Confidence and metadata
                confidence = result.get("confidence", 0.0)
                processing_time = result.get("processing_time", 0.0)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Confidence", f"{confidence:.2f}")
                with col2:
                    st.metric("Processing Time", f"{processing_time:.2f}s")
                with col3:
                    st.metric("Sources Used", result.get("sources_used", 0))
                
                # Save to conversation history
                st.session_state.conversation_history.append({
                    "question": user_query,
                    "answer": answer,
                    "most_relevant_pages": most_relevant_pages,
                    "confidence": confidence,
                    "timestamp": result.get("timestamp")
                })
                
                # Save query log
                st.session_state.query_logs.append(result)
                
            except Exception as e:
                st.error(f"❌ Error processing query: {str(e)}")
                logger.error(f"Error in main query processing: {str(e)}")

if __name__ == "__main__":
    main()
