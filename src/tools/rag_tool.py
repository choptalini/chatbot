"""
RAG tool implementation for the ECLA AI Customer Support Agent.
Provides agentic RAG with semantic similarity search, document grading, and query rewriting.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from langchain.tools import tool
from langchain.schema import Document
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.data.knowledge_base import get_knowledge_base, initialize_knowledge_base

# Set up logging
logger = logging.getLogger(__name__)

# Initialize a separate model for document grading and query rewriting
grading_model = init_chat_model(
    model="gpt-4o-mini",
    model_provider="openai",
    temperature=0.1,
    max_tokens=300,
    api_key=settings.openai_api_key,
)

class RAGInput(BaseModel):
    """Input schema for the RAG tool."""
    query: str = Field(description="The user's question or query about ECLA products")
    max_documents: int = Field(default=5, description="Maximum number of documents to retrieve")
    score_threshold: float = Field(default=0.3, description="Minimum relevance score threshold")

class DocumentGrade(BaseModel):
    """Schema for document grading."""
    score: str = Field(description="Relevance score: 'yes' if relevant, 'no' if not relevant")
    reasoning: str = Field(description="Brief reasoning for the score")

class QueryRewriteResult(BaseModel):
    """Schema for query rewriting result."""
    rewritten_query: str = Field(description="The rewritten query")
    reasoning: str = Field(description="Brief reasoning for the rewrite")

class RAGTool:
    """
    Agentic RAG tool for ECLA customer support.
    Implements document grading, query rewriting, and intelligent retrieval.
    """
    
    def __init__(self):
        """Initialize the RAG tool."""
        self.knowledge_base = get_knowledge_base()
        self.grading_model = grading_model
        self.retrieval_stats = {
            "total_queries": 0,
            "successful_retrievals": 0,
            "failed_retrievals": 0,
            "rewritten_queries": 0,
            "last_updated": datetime.now().isoformat()
        }
        
        # Initialize knowledge base (will only ingest if not already populated)
        try:
            initialize_knowledge_base()
            logger.info("RAG tool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize knowledge base: {e}")
    
    def grade_documents(self, documents: List[Document], query: str) -> List[Dict[str, Any]]:
        """
        Grade documents for relevance to the query.
        
        Args:
            documents: List of retrieved documents
            query: User query
            
        Returns:
            List of graded documents with relevance scores
        """
        try:
            graded_docs = []
            
            # Grading prompt
            grading_prompt = PromptTemplate.from_template(
                """You are a grader assessing the relevance of retrieved documents to a user question about ECLA teeth whitening products.
                
                Here is the retrieved document:
                {document}
                
                Here is the user question:
                {query}
                
                If the document contains information that helps answer the user's question about ECLA products, pricing, usage, or company information, grade it as relevant.
                
                Give a binary score 'yes' or 'no' to indicate whether the document is relevant to the question.
                Provide brief reasoning for your decision.
                
                Score: """
            )
            
            for doc in documents:
                try:
                    # Format the grading prompt
                    formatted_prompt = grading_prompt.format(
                        document=doc.page_content,
                        query=query
                    )
                    
                    # Get grading response
                    response = self.grading_model.invoke([HumanMessage(content=formatted_prompt)])
                    
                    # Parse the response
                    response_text = response.content.lower()
                    is_relevant = 'yes' in response_text
                    
                    graded_docs.append({
                        'document': doc,
                        'relevant': is_relevant,
                        'grade_response': response.content,
                        'metadata': doc.metadata
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to grade document: {e}")
                    # Default to relevant if grading fails
                    graded_docs.append({
                        'document': doc,
                        'relevant': True,
                        'grade_response': "Grading failed, defaulting to relevant",
                        'metadata': doc.metadata
                    })
            
            relevant_count = sum(1 for doc in graded_docs if doc['relevant'])
            logger.info(f"Graded {len(documents)} documents, {relevant_count} relevant")
            
            return graded_docs
            
        except Exception as e:
            logger.error(f"Document grading failed: {e}")
            # Return all documents as relevant if grading fails
            return [{'document': doc, 'relevant': True, 'grade_response': "Grading failed", 'metadata': doc.metadata} for doc in documents]
    
    def rewrite_query(self, original_query: str, context: str = "") -> str:
        """
        Rewrite the query for better retrieval when initial results are poor.
        
        Args:
            original_query: The original user query
            context: Additional context about why rewriting is needed
            
        Returns:
            Rewritten query
        """
        try:
            rewrite_prompt = PromptTemplate.from_template(
                """You are a query rewriter for a customer support system for ECLA teeth whitening products.
                
                The original query didn't return relevant results. Rewrite it to be more specific to ECLA products and services.
                
                Original query: {original_query}
                Context: {context}
                
                Focus on these ECLA products and topics:
                - ECLA® e20 Bionic⁺ Kit ($55) - LED whitening system
                - ECLA® Purple Corrector ($26) - Color correcting serum
                - ECLA® Teeth Whitening Pen ($20) - Portable whitening pen
                - Usage instructions and safety information
                - Company information and contact details
                - Shipping and delivery information
                
                Rewrite the query to be more likely to retrieve relevant ECLA product information:
                """
            )
            
            # Format the rewrite prompt
            formatted_prompt = rewrite_prompt.format(
                original_query=original_query,
                context=context
            )
            
            # Get rewritten query
            response = self.grading_model.invoke([HumanMessage(content=formatted_prompt)])
            rewritten_query = response.content.strip()
            
            logger.info(f"Query rewritten from '{original_query}' to '{rewritten_query}'")
            self.retrieval_stats["rewritten_queries"] += 1
            
            return rewritten_query
            
        except Exception as e:
            logger.error(f"Query rewriting failed: {e}")
            # Return original query if rewriting fails
            return original_query
    
    def retrieve_documents(self, query: str, max_documents: int = 5, score_threshold: float = 0.3) -> List[Document]:
        """
        Retrieve relevant documents from the knowledge base.
        
        Args:
            query: Search query
            max_documents: Maximum number of documents to return
            score_threshold: Minimum relevance score threshold
            
        Returns:
            List of relevant documents
        """
        try:
            self.retrieval_stats["total_queries"] += 1
            
            # Initial retrieval
            documents = self.knowledge_base.search_knowledge_base(
                query, 
                k=max_documents, 
                score_threshold=score_threshold
            )
            
            if not documents:
                logger.warning(f"No documents found for query: {query}")
                
                # Try with a rewritten query
                rewritten_query = self.rewrite_query(query, "No documents found with original query")
                documents = self.knowledge_base.search_knowledge_base(
                    rewritten_query, 
                    k=max_documents, 
                    score_threshold=score_threshold * 0.8  # Lower threshold for rewritten query
                )
            
            if documents:
                self.retrieval_stats["successful_retrievals"] += 1
                logger.info(f"Successfully retrieved {len(documents)} documents")
            else:
                self.retrieval_stats["failed_retrievals"] += 1
                logger.warning("No documents found even after query rewriting")
            
            return documents
            
        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            self.retrieval_stats["failed_retrievals"] += 1
            return []
    
    def format_response(self, query: str, graded_docs: List[Dict[str, Any]]) -> str:
        """
        Format the final response based on retrieved and graded documents.
        
        Args:
            query: Original user query
            graded_docs: List of graded documents
            
        Returns:
            Formatted response string
        """
        try:
            # Filter for relevant documents
            relevant_docs = [doc for doc in graded_docs if doc['relevant']]
            
            if not relevant_docs:
                return (
                    "I couldn't find specific information about that in our ECLA product database. "
                    "However, I can help you with information about our teeth whitening products:\n\n"
                    "• ECLA® e20 Bionic⁺ Kit ($55) - Professional LED whitening system\n"
                    "• ECLA® Purple Corrector ($26) - Color correcting serum\n"
                    "• ECLA® Teeth Whitening Pen ($20) - Portable whitening pen\n\n"
                    "For more specific information, please contact us at +961 76380144 or info@ecladerm.com."
                )
            
            # Combine information from relevant documents
            combined_info = []
            for doc_info in relevant_docs:
                doc = doc_info['document']
                combined_info.append(doc.page_content)
            
            # Create context for response formatting
            context = "\n\n".join(combined_info)
            
            # Format response using the grading model
            response_prompt = PromptTemplate.from_template(
                """You are ECLA's customer support agent. Based on the following information from our knowledge base, provide a helpful and accurate response to the customer's question.
                
                Customer Question: {query}
                
                Relevant Information:
                {context}
                
                Instructions:
                - Be friendly and professional
                - Provide accurate information about ECLA products
                - Include prices when relevant
                - Mention contact information if needed
                - If discussing safety or medical aspects, be cautious and recommend consulting a dentist
                - Keep the response concise but complete
                
                Response:"""
            )
            
            formatted_prompt = response_prompt.format(
                query=query,
                context=context
            )
            
            response = self.grading_model.invoke([HumanMessage(content=formatted_prompt)])
            
            return response.content
            
        except Exception as e:
            logger.error(f"Response formatting failed: {e}")
            return (
                "I encountered an error while processing your request. "
                "Please contact our support team at +961 76380144 or info@ecladerm.com for assistance."
            )
    
    def search(self, query: str, max_documents: int = 5, score_threshold: float = 0.3) -> str:
        """
        Main search method that orchestrates the entire RAG process.
        
        Args:
            query: User query
            max_documents: Maximum number of documents to retrieve
            score_threshold: Minimum relevance score threshold
            
        Returns:
            Formatted response string
        """
        try:
            logger.info(f"Starting RAG search for query: {query}")
            
            # Step 1: Retrieve documents
            documents = self.retrieve_documents(query, max_documents, score_threshold)
            
            if not documents:
                return (
                    "I couldn't find specific information about that in our knowledge base. "
                    "Let me help you with our ECLA teeth whitening products:\n\n"
                    "• ECLA® e20 Bionic⁺ Kit ($55) - Professional LED whitening system\n"
                    "• ECLA® Purple Corrector ($26) - Color correcting serum\n"
                    "• ECLA® Teeth Whitening Pen ($20) - Portable whitening pen\n\n"
                    "For more specific information, please contact us at +961 76380144 or info@ecladerm.com."
                )
            
            # Step 2: Grade documents for relevance
            graded_docs = self.grade_documents(documents, query)
            
            # Step 3: Format response
            response = self.format_response(query, graded_docs)
            
            logger.info("RAG search completed successfully")
            return response
            
        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return (
                "I encountered an error while searching for information. "
                "Please contact our support team at +961 76380144 or info@ecladerm.com for assistance."
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get RAG tool statistics.
        
        Returns:
            Dictionary with statistics
        """
        self.retrieval_stats["last_updated"] = datetime.now().isoformat()
        
        # Add knowledge base stats
        kb_stats = self.knowledge_base.get_collection_stats()
        
        return {
            "retrieval_stats": self.retrieval_stats,
            "knowledge_base_stats": kb_stats,
            "tool_name": "ecla_rag_tool",
            "version": "1.0.0"
        }

# Global RAG tool instance
_rag_tool_instance = None

def get_rag_tool() -> RAGTool:
    """
    Get the global RAG tool instance.
    
    Returns:
        RAGTool instance
    """
    global _rag_tool_instance
    if _rag_tool_instance is None:
        _rag_tool_instance = RAGTool()
    return _rag_tool_instance

# Define the tool for LangGraph
@tool("ecla_rag_search", args_schema=RAGInput, return_direct=False)
def rag_tool(query: str, max_documents: int = 5, score_threshold: float = 0.3) -> str:
    """
    Search ECLA knowledge base for product information, usage instructions, and company details.
    
    Use this tool when customers ask about:
    - ECLA product information and pricing
    - Usage instructions and safety information
    - Company contact details and shipping information
    - Product comparisons and recommendations
    
    Args:
        query: The customer's question or query
        max_documents: Maximum number of documents to retrieve (default: 5)
        score_threshold: Minimum relevance score threshold (default: 0.3)
        
    Returns:
        Formatted response with relevant ECLA information
    """
    try:
        rag_instance = get_rag_tool()
        response = rag_instance.search(query, max_documents, score_threshold)
        
        logger.info(f"RAG tool called with query: {query}")
        return response
        
    except Exception as e:
        logger.error(f"RAG tool failed: {e}")
        return (
            "I encountered an error while searching for information. "
            "Please contact our support team at +961 76380144 or info@ecladerm.com for assistance."
        )

# Convenience functions
def search_ecla_products(query: str) -> str:
    """
    Convenience function to search ECLA products.
    
    Args:
        query: Search query
        
    Returns:
        Search results
    """
    return rag_tool(query)

def get_rag_stats() -> Dict[str, Any]:
    """
    Get RAG tool statistics.
    
    Returns:
        Dictionary with statistics
    """
    rag_instance = get_rag_tool()
    return rag_instance.get_stats()

# Export the tool for use in the agent
__all__ = ['rag_tool', 'search_ecla_products', 'get_rag_stats'] 