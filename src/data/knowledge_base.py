"""
ECLA knowledge base setup and chunking for RAG tool.
Contains product information, company details, and usage instructions.
"""

import os
import logging
from typing import List, Dict, Any
from datetime import datetime

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from src.config.settings import settings

# Set up logging
logger = logging.getLogger(__name__)

# ECLA Product Information (from the PRD)
ECLA_KNOWLEDGE_BASE = {
    "products": {
        "e20_bionic_kit": {
            "name": "ECLA® e20 Bionic⁺ Kit",
            "price": "$55.00 USD",
            "description": "Professional teeth whitening system featuring LED light technology for accelerated results. Includes whitening gel and step-by-step instructions. Safe for enamel with gentle formula designed for home use.",
            "features": [
                "LED light technology for accelerated whitening",
                "Professional-level results at home",
                "Gentle formula safe for enamel",
                "Comprehensive kit with gel and instructions",
                "Easy-to-use system"
            ],
            "usage": "Apply gel to teeth, insert LED light, activate for recommended time. Follow included safety guidelines and usage frequency recommendations.",
            "category": "comprehensive_whitening_system"
        },
        "purple_corrector": {
            "name": "ECLA® Purple Corrector",
            "price": "$26.00 USD",
            "description": "Color-correcting serum using advanced purple toning technology to instantly neutralize yellow tones on teeth. Perfect for maintenance between whitening sessions.",
            "features": [
                "Advanced purple toning technology",
                "Instant yellow tone neutralization",
                "Perfect for maintenance",
                "Quick application",
                "Visible results immediately"
            ],
            "usage": "Apply thin layer to clean teeth, leave for specified time, rinse thoroughly. Use as needed for color correction.",
            "category": "color_corrector"
        },
        "whitening_pen": {
            "name": "ECLA® Teeth Whitening Pen",
            "price": "$20.00 USD",
            "description": "Convenient portable pen for on-the-go touch-ups and targeted whitening. Easy application for busy lifestyles.",
            "features": [
                "Portable and convenient",
                "On-the-go touch-ups",
                "Targeted whitening",
                "Easy application",
                "Perfect for busy lifestyles"
            ],
            "usage": "Clean teeth, apply gel precisely to target areas, avoid contact with gums, rinse after recommended time.",
            "category": "portable_whitening"
        }
    },
    "company_info": {
        "name": "ECLA",
        "website": "eclasmile.com",
        "address": "Enipharma Building, Dmit-Beit Ed Dine Main Road, Dmit, Chouf, Lebanon",
        "phone": "+961 76380144",
        "email": "info@ecladerm.com",
        "description": "Lebanese company specializing in at-home teeth whitening products. Professional-level results with home convenience. Safe, effective, and gentle on tooth enamel.",
        "target_market": "Lebanese and greater Middle Eastern markets",
        "special_offers": "Free delivery throughout Lebanon"
    },
    "safety_information": {
        "general_safety": "All ECLA products are formulated to be gentle on tooth enamel. Discontinue use if sensitivity occurs. Consult dentist before use if you have dental conditions.",
        "age_restrictions": "Not recommended for children under 16.",
        "precautions": "Keep away from eyes and sensitive gum areas.",
        "side_effects": "Some users may experience temporary tooth sensitivity. This is normal and should subside within 24-48 hours.",
        "contraindications": "Do not use if you have active dental work, cavities, or gum disease without consulting a dentist first."
    },
    "usage_instructions": {
        "general_tips": [
            "Clean teeth thoroughly before application",
            "Follow recommended usage frequency",
            "Avoid eating or drinking for 30 minutes after application",
            "Store products in a cool, dry place",
            "Do not exceed recommended application time"
        ],
        "expected_results": "Results may vary depending on individual tooth condition and consistency of use. Most users see noticeable improvements within 7-14 days of regular use.",
        "maintenance": "For best results, use ECLA® Purple Corrector between whitening sessions to maintain color and neutralize yellow tones."
    },
    "faq": {
        "how_long_to_see_results": "Most users see noticeable improvements within 7-14 days of regular use, with optimal results achieved after 2-3 weeks of consistent application.",
        "frequency_of_use": "For the e20 Bionic⁺ Kit, use 2-3 times per week. Purple Corrector can be used daily as needed. Whitening Pen is perfect for touch-ups as required.",
        "sensitivity_concerns": "Our products are formulated to be gentle on enamel. If you experience sensitivity, reduce usage frequency or discontinue use and consult a dentist.",
        "shipping_info": "We offer free delivery throughout Lebanon. International shipping is available for other Middle Eastern countries.",
        "product_shelf_life": "All ECLA products have a shelf life of 24 months from manufacture date when stored properly."
    }
}

class ECLAKnowledgeBase:
    """
    ECLA Knowledge Base manager for RAG implementation.
    Handles document chunking, embedding, and vector storage.
    """
    
    def __init__(self, persist_directory: str = None):
        """
        Initialize the ECLA knowledge base.
        
        Args:
            persist_directory: Directory to persist the vector database
        """
        self.persist_directory = persist_directory or settings.chroma_persist_directory
        self.embeddings = None
        self.vector_store = None
        self.text_splitter = None
        
        # Initialize components
        self._setup_embeddings()
        self._setup_text_splitter()
        self._setup_vector_store()
        
        logger.info("ECLA Knowledge Base initialized")
    
    def _setup_embeddings(self):
        """Setup OpenAI embeddings for document vectorization."""
        try:
            self.embeddings = OpenAIEmbeddings(
                openai_api_key=settings.openai_api_key,
                model="text-embedding-3-small"  # More cost-effective embedding model
            )
            logger.info("OpenAI embeddings initialized")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")
            raise
    
    def _setup_text_splitter(self):
        """Setup text splitter for document chunking."""
        # Using 300 characters with 100 overlap as specified in the PRD
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=300,
            chunk_overlap=100,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        logger.info("Text splitter initialized with 300 char chunks, 100 overlap")
    
    def _setup_vector_store(self):
        """Setup Chroma vector store for document storage and retrieval."""
        try:
            # Create persist directory if it doesn't exist
            if not os.path.exists(self.persist_directory):
                os.makedirs(self.persist_directory)
            
            # Initialize Chroma vector store
            self.vector_store = Chroma(
                collection_name="ecla_knowledge_base",
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            
            logger.info(f"Chroma vector store initialized at {self.persist_directory}")
            
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise

    def is_knowledge_base_populated(self) -> bool:
        """
        Check if the knowledge base already has documents.
        
        Returns:
            True if knowledge base has documents, False otherwise
        """
        try:
            collection = self.vector_store._collection
            count = collection.count()
            logger.info(f"Knowledge base has {count} documents")
            return count > 0
        except Exception as e:
            logger.error(f"Failed to check knowledge base population: {e}")
            return False
    
    def _convert_to_documents(self) -> List[Document]:
        """
        Convert ECLA knowledge base to LangChain Document objects.
        
        Returns:
            List of Document objects
        """
        documents = []
        
        # Process products
        for product_key, product_info in ECLA_KNOWLEDGE_BASE["products"].items():
            # Main product document
            product_text = f"""
            {product_info['name']} - {product_info['price']}
            
            {product_info['description']}
            
            Features:
            {chr(10).join(f"• {feature}" for feature in product_info['features'])}
            
            Usage Instructions:
            {product_info['usage']}
            
            Category: {product_info['category']}
            """
            
            documents.append(Document(
                page_content=product_text.strip(),
                metadata={
                    "type": "product",
                    "product_name": product_info['name'],
                    "price": product_info['price'],
                    "category": product_info['category'],
                    "source": f"ecla_product_{product_key}"
                }
            ))
        
        # Process company information
        company_info = ECLA_KNOWLEDGE_BASE["company_info"]
        company_text = f"""
        About ECLA
        
        ECLA is a {company_info['description']}
        
        Contact Information:
        • Website: {company_info['website']}
        • Address: {company_info['address']}
        • Phone: {company_info['phone']}
        • Email: {company_info['email']}
        
        Target Market: {company_info['target_market']}
        Special Offers: {company_info['special_offers']}
        """
        
        documents.append(Document(
            page_content=company_text.strip(),
            metadata={
                "type": "company_info",
                "source": "ecla_company_info"
            }
        ))
        
        # Process safety information
        safety_info = ECLA_KNOWLEDGE_BASE["safety_information"]
        safety_text = f"""
        Safety Information for ECLA Products
        
        General Safety: {safety_info['general_safety']}
        
        Age Restrictions: {safety_info['age_restrictions']}
        
        Precautions: {safety_info['precautions']}
        
        Side Effects: {safety_info['side_effects']}
        
        Contraindications: {safety_info['contraindications']}
        """
        
        documents.append(Document(
            page_content=safety_text.strip(),
            metadata={
                "type": "safety_info",
                "source": "ecla_safety_info"
            }
        ))
        
        # Process usage instructions
        usage_info = ECLA_KNOWLEDGE_BASE["usage_instructions"]
        usage_text = f"""
        General Usage Instructions for ECLA Products
        
        General Tips:
        {chr(10).join(f"• {tip}" for tip in usage_info['general_tips'])}
        
        Expected Results: {usage_info['expected_results']}
        
        Maintenance: {usage_info['maintenance']}
        """
        
        documents.append(Document(
            page_content=usage_text.strip(),
            metadata={
                "type": "usage_instructions",
                "source": "ecla_usage_info"
            }
        ))
        
        # Process FAQ
        faq_info = ECLA_KNOWLEDGE_BASE["faq"]
        for question, answer in faq_info.items():
            faq_text = f"""
            FAQ: {question.replace('_', ' ').title()}
            
            {answer}
            """
            
            documents.append(Document(
                page_content=faq_text.strip(),
                metadata={
                    "type": "faq",
                    "question": question,
                    "source": f"ecla_faq_{question}"
                }
            ))
        
        logger.info(f"Generated {len(documents)} documents from knowledge base")
        return documents
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """
        Chunk documents using the text splitter.
        
        Args:
            documents: List of documents to chunk
            
        Returns:
            List of chunked documents
        """
        try:
            chunked_docs = self.text_splitter.split_documents(documents)
            logger.info(f"Chunked {len(documents)} documents into {len(chunked_docs)} chunks")
            return chunked_docs
        except Exception as e:
            logger.error(f"Failed to chunk documents: {e}")
            raise
    
    def ingest_knowledge_base(self) -> bool:
        """
        Ingest the ECLA knowledge base into the vector store.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert knowledge base to documents
            documents = self._convert_to_documents()
            
            # Chunk the documents
            chunked_docs = self.chunk_documents(documents)
            
            # Add to vector store
            self.vector_store.add_documents(chunked_docs)
            
            logger.info(f"Successfully ingested {len(chunked_docs)} document chunks")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ingest knowledge base: {e}")
            return False
    
    def search_knowledge_base(self, query: str, k: int = 5, score_threshold: float = 0.3) -> List[Document]:
        """
        Search the knowledge base for relevant documents.
        
        Args:
            query: Search query
            k: Number of documents to return
            score_threshold: Minimum similarity score threshold
            
        Returns:
            List of relevant documents
        """
        try:
            # Perform similarity search with score
            docs_with_scores = self.vector_store.similarity_search_with_score(
                query, 
                k=k
            )
            
            # Filter by score threshold
            relevant_docs = []
            for doc, score in docs_with_scores:
                # Convert distance to similarity (lower distance = higher similarity)
                similarity = 1 - score
                if similarity >= score_threshold:
                    relevant_docs.append(doc)
            
            logger.info(f"Found {len(relevant_docs)} relevant documents for query: {query}")
            return relevant_docs
            
        except Exception as e:
            logger.error(f"Failed to search knowledge base: {e}")
            return []
    
    def get_product_info(self, product_name: str) -> Dict[str, Any]:
        """
        Get specific product information by name.
        
        Args:
            product_name: Name of the product
            
        Returns:
            Product information dictionary
        """
        try:
            # Search for the product
            docs = self.search_knowledge_base(f"product {product_name}", k=3)
            
            product_info = {}
            for doc in docs:
                if doc.metadata.get("type") == "product":
                    product_info = {
                        "name": doc.metadata.get("product_name"),
                        "price": doc.metadata.get("price"),
                        "category": doc.metadata.get("category"),
                        "content": doc.page_content
                    }
                    break
            
            return product_info
            
        except Exception as e:
            logger.error(f"Failed to get product info: {e}")
            return {}
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge base collection.
        
        Returns:
            Dictionary with collection statistics
        """
        try:
            # Get collection
            collection = self.vector_store._collection
            
            stats = {
                "total_documents": collection.count(),
                "collection_name": collection.name,
                "persist_directory": self.persist_directory,
                "embedding_model": "text-embedding-3-small",
                "chunk_size": 300,
                "chunk_overlap": 100,
                "last_updated": datetime.now().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"error": str(e)}
    
    def reset_knowledge_base(self) -> bool:
        """
        Reset the knowledge base by clearing all documents.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete the collection
            self.vector_store._client.delete_collection(self.vector_store._collection.name)
            
            # Recreate the vector store
            self._setup_vector_store()
            
            logger.info("Knowledge base reset successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset knowledge base: {e}")
            return False


# Global knowledge base instance
_knowledge_base = None

def get_knowledge_base() -> ECLAKnowledgeBase:
    """
    Get the global knowledge base instance.
    
    Returns:
        ECLAKnowledgeBase instance
    """
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = ECLAKnowledgeBase()
    return _knowledge_base

def initialize_knowledge_base() -> bool:
    """
    Initialize and ingest the knowledge base.
    
    Returns:
        True if successful, False otherwise
    """
    kb = get_knowledge_base()
    if not kb.is_knowledge_base_populated():
        return kb.ingest_knowledge_base()
    else:
        logger.info("Knowledge base already populated, skipping ingestion.")
        return True

def search_ecla_knowledge(query: str, k: int = 5) -> List[Document]:
    """
    Search the ECLA knowledge base.
    
    Args:
        query: Search query
        k: Number of results to return
        
    Returns:
        List of relevant documents
    """
    kb = get_knowledge_base()
    return kb.search_knowledge_base(query, k)

def get_ecla_product_info(product_name: str) -> Dict[str, Any]:
    """
    Get specific ECLA product information.
    
    Args:
        product_name: Name of the product
        
    Returns:
        Product information dictionary
    """
    kb = get_knowledge_base()
    return kb.get_product_info(product_name)

def get_knowledge_base_stats() -> Dict[str, Any]:
    """
    Get knowledge base statistics.
    
    Returns:
        Dictionary with statistics
    """
    kb = get_knowledge_base()
    return kb.get_collection_stats() 