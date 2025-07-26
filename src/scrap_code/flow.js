/**
 * WhatsApp Flow Logic
 * 
 * This file contains the business logic for navigating between Flow screens
 * and handling data exchange requests.
 * 
 * ⚠️ WARNING: This is for prototyping only, not production ready.
 */

/**
 * Handle data exchange requests from WhatsApp Flow
 * @param {Object} requestData - Decrypted request data from WhatsApp
 * @returns {Object} Response object with screen and data
 */
function handleDataExchange(requestData) {
    const { action, screen, data, flow_token } = requestData;

    console.log(`📨 Flow Request - Action: ${action}, Screen: ${screen}`);
    console.log('📋 Request Data:', data);

    switch (action) {
        case 'INIT':
            return handleFlowInit(flow_token, data);
        
        case 'data_exchange':
            return handleScreenSubmission(screen, data, flow_token);
        
        case 'BACK':
            return handleBackNavigation(screen, data, flow_token);
        
        default:
            console.error('❌ Unknown action:', action);
            return {
                screen: screen || 'WELCOME',
                data: {
                    error_message: 'Unknown action type'
                }
            };
    }
}

/**
 * Handle Flow initialization
 * @param {string} flowToken - Flow session token
 * @param {Object} data - Initial data
 * @returns {Object} Response for initial screen
 */
function handleFlowInit(flowToken, data) {
    console.log('🚀 Initializing Flow with token:', flowToken);
    
    // Return the first screen of your Flow
    return {
        screen: 'WELCOME',
        data: {
            welcome_message: 'Welcome to our service!',
            user_name: data?.user_name || 'Guest',
            timestamp: new Date().toISOString()
        }
    };
}

/**
 * Handle screen submission and navigation
 * @param {string} currentScreen - Current screen name
 * @param {Object} data - Form data from the screen
 * @param {string} flowToken - Flow session token
 * @returns {Object} Response with next screen or completion
 */
function handleScreenSubmission(currentScreen, data, flowToken) {
    console.log(`📋 Screen Submission - Current: ${currentScreen}`);
    
    switch (currentScreen) {
        case 'WELCOME':
            return handleWelcomeSubmission(data, flowToken);
        
        case 'FORM':
            return handleFormSubmission(data, flowToken);
        
        case 'CONFIRMATION':
            return handleConfirmationSubmission(data, flowToken);
        
        default:
            console.error('❌ Unknown screen:', currentScreen);
            return {
                screen: 'WELCOME',
                data: {
                    error_message: 'Invalid screen navigation'
                }
            };
    }
}

/**
 * Handle welcome screen submission
 */
function handleWelcomeSubmission(data, flowToken) {
    // Example: User clicked "Get Started" button
    if (data.action === 'get_started') {
        return {
            screen: 'FORM',
            data: {
                form_title: 'Please fill out your information',
                user_name: data.user_name || '',
                email: data.email || ''
            }
        };
    }
    
    return {
        screen: 'WELCOME',
        data: {
            error_message: 'Please click Get Started to continue'
        }
    };
}

/**
 * Handle form screen submission
 */
function handleFormSubmission(data, flowToken) {
    // Validate form data
    const errors = validateFormData(data);
    
    if (errors.length > 0) {
        return {
            screen: 'FORM',
            data: {
                ...data,
                error_message: `Please fix the following: ${errors.join(', ')}`
            }
        };
    }
    
    // Form is valid, proceed to confirmation
    return {
        screen: 'CONFIRMATION',
        data: {
            user_name: data.user_name,
            email: data.email,
            phone: data.phone,
            confirmation_message: 'Please confirm your information is correct'
        }
    };
}

/**
 * Handle confirmation screen submission (Flow completion)
 */
function handleConfirmationSubmission(data, flowToken) {
    if (data.action === 'confirm') {
        // Complete the Flow and send response message
        return {
            screen: 'SUCCESS',
            data: {
                extension_message_response: {
                    params: {
                        flow_token: flowToken,
                        user_name: data.user_name,
                        email: data.email,
                        phone: data.phone,
                        completion_time: new Date().toISOString()
                    }
                }
            }
        };
    } else if (data.action === 'edit') {
        // Go back to form for editing
        return {
            screen: 'FORM',
            data: {
                user_name: data.user_name,
                email: data.email,
                phone: data.phone,
                form_title: 'Edit your information'
            }
        };
    }
    
    return {
        screen: 'CONFIRMATION',
        data: {
            ...data,
            error_message: 'Please confirm or choose to edit your information'
        }
    };
}

/**
 * Handle back button navigation
 * @param {string} currentScreen - Current screen name
 * @param {Object} data - Current screen data
 * @param {string} flowToken - Flow session token
 * @returns {Object} Response for previous screen
 */
function handleBackNavigation(currentScreen, data, flowToken) {
    console.log(`⬅️ Back Navigation from: ${currentScreen}`);
    
    switch (currentScreen) {
        case 'FORM':
            return {
                screen: 'WELCOME',
                data: {
                    welcome_message: 'Welcome back!',
                    user_name: data.user_name || 'Guest'
                }
            };
        
        case 'CONFIRMATION':
            return {
                screen: 'FORM',
                data: {
                    user_name: data.user_name,
                    email: data.email,
                    phone: data.phone,
                    form_title: 'Please fill out your information'
                }
            };
        
        default:
            return {
                screen: 'WELCOME',
                data: {
                    welcome_message: 'Welcome to our service!'
                }
            };
    }
}

/**
 * Validate form data
 * @param {Object} data - Form data to validate
 * @returns {Array} Array of error messages
 */
function validateFormData(data) {
    const errors = [];
    
    if (!data.user_name || data.user_name.trim().length < 2) {
        errors.push('Name must be at least 2 characters');
    }
    
    if (!data.email || !/\S+@\S+\.\S+/.test(data.email)) {
        errors.push('Valid email is required');
    }
    
    if (!data.phone || data.phone.length < 10) {
        errors.push('Valid phone number is required');
    }
    
    return errors;
}

/**
 * Handle health check requests
 * @returns {Object} Health check response
 */
function handleHealthCheck() {
    return {
        data: {
            status: 'active'
        }
    };
}

/**
 * Handle error notification requests
 * @param {Object} errorData - Error information from WhatsApp
 * @returns {Object} Error acknowledgment response
 */
function handleErrorNotification(errorData) {
    console.error('❌ Flow Error Notification:', errorData);
    
    return {
        data: {
            acknowledged: true
        }
    };
}

module.exports = {
    handleDataExchange,
    handleHealthCheck,
    handleErrorNotification
}; 