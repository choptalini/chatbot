# 📋 Product Requirements Document (PRD)
## Infobip WhatsApp Methods SDK

**Version**: 1.0  
**Date**: December 2024  
**Author**: ECLA Development Team  
**Status**: Planning Phase  

---

## 📊 Executive Summary

### Problem Statement
Currently, WhatsApp functionality using Infobip API is scattered across 8+ separate Python files with duplicated code, inconsistent error handling, and no centralized configuration. This creates maintenance issues and makes the codebase difficult to extend or reuse.

### Solution Overview
Create a unified **`infobip_whatsapp_methods`** SDK that consolidates all WhatsApp Business API functionality into a clean, professional, and reusable Python package.

### Business Impact
- **Reduced development time** by 60% for new WhatsApp features
- **Improved code maintainability** and consistency
- **Enhanced developer experience** with simple import/usage
- **Increased system reliability** through centralized error handling

---

## 🎯 Product Overview

### What We're Building
A comprehensive Python SDK for Infobip WhatsApp Business API that provides:
- **Unified client interface** for all WhatsApp operations
- **Professional API design** with consistent method signatures
- **Comprehensive error handling** and logging
- **Input validation** and type safety
- **Flexible configuration** system
- **Production-ready features** (rate limiting, retries, monitoring)

### Current State Analysis
```
Existing Files (8 scattered scripts):
├── send_response_message.py      → 150 lines, basic text sending
├── send_whatsapp_image.py        → 200 lines, image handling
├── send_whatsapp_location.py     → 180 lines, location messages
├── send_template_message.py      → 160 lines, template support
├── whatsapp_media_handler.py     → 300 lines, media download
├── mark_message_read.py          → 100 lines, read receipts
├── auto_responder.py            → 200 lines, auto-responses
└── Common issues: Duplicated auth, inconsistent errors
```

### Target State
```
New SDK Structure:
├── infobip_whatsapp_methods/
│   ├── __init__.py              → Clean imports
│   ├── client.py               → Main WhatsAppClient class
│   ├── exceptions.py           → Custom exceptions
│   ├── utils.py               → Helper functions
│   ├── constants.py           → API endpoints
│   ├── validators.py          → Input validation
│   └── README.md             → Documentation
```

---

## 🏆 Goals and Objectives

### Primary Goals
1. **Consolidate** all scattered WhatsApp functionality into one SDK
2. **Improve** developer experience with simple, consistent API
3. **Enhance** code maintainability and reusability
4. **Eliminate** code duplication and inconsistencies
5. **Provide** production-ready error handling and logging

### Success Metrics
- **100% feature parity** with existing scattered files
- **Single import statement** replaces 8+ individual files
- **Zero breaking changes** to existing integrations
- **Comprehensive test coverage** (>90%)
- **Complete documentation** with examples

### Non-Goals
- **Not building new WhatsApp features** - only consolidating existing ones
- **Not changing webhook server** - keep whatsapp_message_fetcher.py
- **Not modifying feed functionality** - keep whatsapp_feed.py

---

## 👥 User Stories

### As a Developer
- **I want** to import one client instead of managing 8+ files
- **I want** consistent error handling across all WhatsApp operations
- **I want** clear documentation and examples for every method
- **I want** type hints and IDE autocompletion support

### As a System Administrator
- **I want** centralized logging for all WhatsApp operations
- **I want** configurable rate limiting and retry policies
- **I want** monitoring and metrics for API usage
- **I want** easy deployment and configuration management

### As an AI Agent Developer
- **I want** to easily integrate WhatsApp messaging into agent tools
- **I want** reliable error handling that doesn't break agent flow
- **I want** flexible response generation capabilities
- **I want** seamless integration with existing agent architecture

---

## ⚙️ Functional Requirements

### FR-1: Core Messaging Methods

#### FR-1.1: Text Messages
```python
client.send_text_message(
    to_number: str,
    message: str,
    **kwargs
) -> MessageResponse
```
- **Input validation**: Phone number format, message length
- **Features**: Rich text support, emoji handling
- **Error handling**: Network failures, invalid recipients

#### FR-1.2: Image Messages
```python
client.send_image(
    to_number: str,
    media_url: str,
    caption: str = "",
    **kwargs
) -> MessageResponse
```
- **Supported formats**: JPEG, PNG, WebP, GIF
- **Validation**: URL accessibility, file size limits
- **Features**: Caption support, format detection

#### FR-1.3: Location Messages
```python
client.send_location(
    to_number: str,
    latitude: float,
    longitude: float,
    name: str = "",
    address: str = "",
    **kwargs
) -> MessageResponse
```
- **Validation**: Coordinate ranges, string lengths
- **Features**: Lebanon preset locations, address formatting
- **Error handling**: Invalid coordinates, geocoding failures

#### FR-1.4: Template Messages
```python
client.send_template(
    to_number: str,
    template_name: str,
    variables: List[str] = [],
    **kwargs
) -> MessageResponse
```
- **Features**: Variable substitution, button support
- **Validation**: Template existence, variable count
- **Error handling**: Template approval status

### FR-2: Media Handling

#### FR-2.1: Media Download
```python
client.download_media(
    media_url: str,
    save_path: str = None,
    **kwargs
) -> MediaDownloadResponse
```
- **Features**: Automatic file naming, metadata extraction
- **Validation**: URL accessibility, storage permissions
- **Error handling**: Download failures, disk space

#### FR-2.2: Media Metadata
```python
client.get_media_metadata(
    media_url: str,
    **kwargs
) -> MediaMetadataResponse
```
- **Features**: File size, type, dimensions
- **Performance**: HEAD requests only
- **Caching**: Metadata caching for performance

### FR-3: Message Status Management

#### FR-3.1: Mark as Read
```python
client.mark_as_read(
    message_id: str,
    **kwargs
) -> StatusResponse
```
- **Features**: Read receipt delivery
- **Validation**: Message ID format
- **Error handling**: Invalid message IDs

### FR-4: Auto-Response System

#### FR-4.1: Intelligent Auto-Responses
```python
client.auto_respond(
    incoming_message: str,
    sender_name: str,
    sender_number: str,
    **kwargs
) -> AutoResponseResult
```
- **Features**: Keyword matching, template selection
- **Customization**: Custom response templates
- **Intelligence**: Context-aware responses

### FR-5: Webhook Utilities

#### FR-5.1: Payload Processing
```python
client.process_webhook_payload(
    payload: dict,
    **kwargs
) -> List[InboundMessage]
```
- **Features**: Message extraction, validation
- **Support**: All Infobip webhook formats
- **Error handling**: Malformed payloads

---

## 🔧 Technical Requirements

### TR-1: Architecture Requirements

#### TR-1.1: Client Design
- **Pattern**: Singleton-like client with configuration
- **Dependencies**: Minimal external dependencies
- **Python Version**: 3.8+ compatibility
- **Thread Safety**: Concurrent request support

#### TR-1.2: Package Structure
```
infobip_whatsapp_methods/
├── __init__.py              # Package exports
├── client.py               # Main WhatsAppClient
├── exceptions.py           # Custom exceptions
├── utils.py               # Helper functions
├── constants.py           # API constants
├── validators.py          # Input validation
├── models.py              # Response models
└── README.md             # Documentation
```

### TR-2: Configuration Management

#### TR-2.1: Environment Variables
```python
INFOBIP_API_KEY=your_api_key
INFOBIP_BASE_URL=your_base_url
WHATSAPP_SENDER=your_sender_number
WHATSAPP_RATE_LIMIT=10  # requests per second
WHATSAPP_TIMEOUT=30     # request timeout
```

#### TR-2.2: Programmatic Configuration
```python
client = WhatsAppClient(
    api_key="key",
    base_url="url",
    sender="number",
    rate_limit=10,
    timeout=30,
    retry_attempts=3
)
```

### TR-3: Error Handling Requirements

#### TR-3.1: Exception Hierarchy
```python
WhatsAppError (base)
├── AuthenticationError
├── RateLimitError
├── ValidationError
├── NetworkError
├── APIError
└── MediaError
```

#### TR-3.2: Retry Logic
- **Exponential backoff** for rate limit errors
- **Configurable retry attempts** (default: 3)
- **Circuit breaker** for persistent failures
- **Timeout handling** with graceful degradation

### TR-4: Logging Requirements

#### TR-4.1: Structured Logging
```python
import logging
logger = logging.getLogger('infobip_whatsapp_methods')

# Log levels:
# DEBUG: Request/response details
# INFO: Successful operations
# WARNING: Recoverable errors
# ERROR: Failed operations
# CRITICAL: System failures
```

#### TR-4.2: Log Format
```
[TIMESTAMP] [LEVEL] [CLIENT_ID] [METHOD] [MESSAGE] [METADATA]
```

### TR-5: Performance Requirements

#### TR-5.1: Response Times
- **Text messages**: < 2 seconds
- **Image messages**: < 5 seconds
- **Location messages**: < 2 seconds
- **Template messages**: < 3 seconds

#### TR-5.2: Throughput
- **Concurrent requests**: 10+ simultaneous
- **Rate limiting**: Configurable per-second limits
- **Memory usage**: < 50MB per client instance

---

## 📋 API Specifications

### Core Client Interface

#### Client Initialization
```python
class WhatsAppClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        sender: str,
        rate_limit: int = 10,
        timeout: int = 30,
        retry_attempts: int = 3,
        logger: logging.Logger = None
    ):
        """Initialize WhatsApp client with configuration."""
```

#### Message Response Format
```python
@dataclass
class MessageResponse:
    success: bool
    message_id: Optional[str]
    status: str
    error: Optional[str]
    timestamp: datetime
    api_cost: Optional[int]
    metadata: Dict[str, Any]
```

### Method Signatures

#### Text Messaging
```python
def send_text_message(
    self,
    to_number: str,
    message: str,
    *,
    from_number: Optional[str] = None,
    callback_data: Optional[str] = None,
    notify_url: Optional[str] = None
) -> MessageResponse:
    """Send text message to WhatsApp number."""
```

#### Image Messaging
```python
def send_image(
    self,
    to_number: str,
    media_url: str,
    caption: str = "",
    *,
    from_number: Optional[str] = None,
    validate_url: bool = True,
    max_file_size: int = 5_000_000  # 5MB
) -> MessageResponse:
    """Send image message with optional caption."""
```

#### Location Messaging
```python
def send_location(
    self,
    to_number: str,
    latitude: float,
    longitude: float,
    name: str = "",
    address: str = "",
    *,
    from_number: Optional[str] = None,
    validate_coordinates: bool = True
) -> MessageResponse:
    """Send location message with coordinates."""
```

### Validation Specifications

#### Phone Number Validation
```python
def validate_phone_number(phone: str) -> bool:
    """Validate international phone number format."""
    # Support formats: +96170895652, 96170895652
    # Length: 8-15 digits
    # Country codes: Configurable whitelist
```

#### Coordinate Validation
```python
def validate_coordinates(lat: float, lon: float) -> bool:
    """Validate latitude/longitude ranges."""
    # Latitude: -90 to +90
    # Longitude: -180 to +180
    # Precision: Up to 6 decimal places
```

#### URL Validation
```python
def validate_media_url(url: str) -> bool:
    """Validate media URL accessibility."""
    # HTTPS required
    # Accessible without authentication
    # Content-Type validation
    # File size limits
```

---

## 🚀 Implementation Plan

### Phase 1: Foundation (Week 1)
- **Task 1-3**: Analysis and SDK structure design
- **Task 4**: Base client implementation with auth
- **Task 13-14**: Error handling and logging setup

### Phase 2: Core Features (Week 2)
- **Task 5-8**: Implement all messaging methods
- **Task 9-10**: Media handling and status methods
- **Task 16-17**: Validation and configuration

### Phase 3: Advanced Features (Week 3)
- **Task 11-12**: Auto-response and webhook helpers
- **Task 18**: Rate limiting implementation
- **Task 15**: Documentation creation

### Phase 4: Integration (Week 4)
- **Task 20-22**: Update AI agent and webhook server
- **Task 23-24**: Cleanup old files and update imports
- **Task 25**: Create usage examples

### Phase 5: Testing & Launch (Week 5)
- **Task 19**: Test suite creation
- **Task 26-27**: Performance and integration testing
- **Task 28-30**: Migration guide and final cleanup

---

## 📊 Success Metrics

### Development Metrics
- **Lines of code reduction**: Target 40% reduction
- **File count reduction**: From 8 files to 1 package
- **Import simplification**: 1 import replaces 8+
- **Test coverage**: Minimum 90% coverage

### Performance Metrics
- **Response time**: < 2s for text, < 5s for media
- **Error rate**: < 1% for valid requests
- **Memory usage**: < 50MB per client instance
- **Concurrent requests**: 10+ simultaneous

### Quality Metrics
- **Zero breaking changes** to existing integrations
- **100% feature parity** with current implementation
- **Comprehensive documentation** for all methods
- **Type hints** for all public interfaces

---

## ⚠️ Risk Assessment

### High Priority Risks

#### R-1: Integration Breaking Changes
- **Risk**: Updates break existing AI agent tools
- **Mitigation**: Comprehensive testing, gradual migration
- **Contingency**: Keep old files until migration complete

#### R-2: Performance Regression
- **Risk**: New SDK slower than current implementation
- **Mitigation**: Performance testing, benchmarking
- **Contingency**: Optimize bottlenecks, consider caching

#### R-3: Missing Functionality
- **Risk**: SDK missing features from original files
- **Mitigation**: Thorough analysis, feature mapping
- **Contingency**: Incremental addition of missing features

### Medium Priority Risks

#### R-4: Configuration Complexity
- **Risk**: New configuration system too complex
- **Mitigation**: Simple defaults, clear documentation
- **Contingency**: Simplified configuration options

#### R-5: Error Handling Changes
- **Risk**: Different error behavior breaks workflows
- **Mitigation**: Error compatibility layer
- **Contingency**: Configurable error handling modes

---

## 📚 Documentation Requirements

### API Documentation
- **Method signatures** with type hints
- **Parameter descriptions** and examples
- **Return value specifications**
- **Error handling documentation**

### Usage Examples
- **Quick start guide** with basic usage
- **Advanced examples** for each feature
- **Integration examples** with AI agent
- **Migration guide** from old files

### Developer Documentation
- **Contributing guidelines**
- **Testing procedures**
- **Release process**
- **Architecture decisions**

---

## 🎯 Definition of Done

### Code Quality
- [ ] All methods implemented with type hints
- [ ] Comprehensive error handling
- [ ] 90%+ test coverage
- [ ] Code review completed
- [ ] Performance benchmarks met

### Integration
- [ ] AI agent tools updated and working
- [ ] Webhook server integration tested
- [ ] All old files safely removed
- [ ] Import statements updated
- [ ] End-to-end testing passed

### Documentation
- [ ] API documentation complete
- [ ] Usage examples created
- [ ] Migration guide written
- [ ] README updated
- [ ] Changelog documented

### Deployment
- [ ] Package structure finalized
- [ ] Installation process tested
- [ ] Configuration validated
- [ ] Production deployment successful
- [ ] Monitoring and alerting configured

---

## 📞 Stakeholders

### Primary Stakeholders
- **Development Team**: Implementation and maintenance
- **AI Agent Team**: Integration and usage
- **System Operations**: Deployment and monitoring

### Secondary Stakeholders
- **QA Team**: Testing and validation
- **Documentation Team**: User guides and API docs
- **Product Team**: Feature requirements and priorities

---

## 📈 Post-Launch Monitoring

### Key Metrics to Track
- **API response times** and error rates
- **Memory usage** and performance
- **Developer adoption** and feedback
- **Integration stability** and issues

### Success Criteria
- **Zero critical bugs** in first month
- **95%+ uptime** for WhatsApp functionality
- **Positive developer feedback** on usability
- **Successful migration** of all existing code

---

*This PRD will be updated as requirements evolve and implementation progresses.* 