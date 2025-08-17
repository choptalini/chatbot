# PRD: AI-Powered Analytics Engine

**Author:** SwiftReplies AI Assistant
**Date:** August 6, 2025
**Status:** In Development

## 1. Overview

This document outlines the requirements for a new AI-Powered Analytics Engine for the SwiftReplies.ai platform. The objective of this project is to provide our users with deep, actionable insights into the performance of their WhatsApp chatbots. The engine will move beyond simple quantitative metrics and leverage a Large Language Model (LLM) to provide qualitative analysis of lead quality, customer satisfaction, and business impact.

## 2. Problem Statement

Our users, who are primarily focused on using their chatbots to generate leads and drive sales, currently lack a comprehensive way to measure the true effectiveness of their AI agents. They can see message counts, but they cannot easily answer critical business questions such as:

*   Which of my leads are most likely to convert?
*   What are my customers most interested in?
*   How satisfied are my customers with the chatbot experience?
*   What is the direct ROI of my chatbot in terms of revenue and operational efficiency?

This lack of deep insight makes it difficult for users to optimize their sales funnels and demonstrate the full value of the SwiftReplies.ai platform.

## 3. Goals and Objectives

*   **Goal 1: Provide Actionable Insights.** The analytics engine must provide metrics that are directly relevant to a business's sales and support operations.
*   **Goal 2: Demonstrate ROI.** The engine must clearly quantify the business impact of the chatbot in terms of revenue and cost savings.
*   **Goal 3: Enhance User Engagement.** By providing valuable insights, we aim to increase user engagement with the platform and help our users get more value from our service.
*   **Goal 4: Maintain Performance.** The analytics process must not impact the real-time performance of the chatbot. It must run asynchronously and not delay the user-facing response time.

## 4. Key Metrics

The analytics engine will generate the following key metrics for each contact after a conversation is completed:

### 4.1. Lead Generation & Engagement
*   **Lead Generation Rate:** Percentage of new conversations identified as a sales lead.
*   **Engagement Score:** An LLM-generated score (1-100) measuring the quality of the interaction.

### 4.2. Interaction Quality & Intent
*   **Lead Temperature:** LLM-based assessment of a lead's readiness to buy (`Cold`, `Warm`, `Hot`).
*   **Top Inquiry Topics:** An AI-powered summary of the most frequent questions, keywords, and products discussed.
*   **Customer Satisfaction (CSAT) Score:** A direct measure of customer happiness, gathered by asking the user for a rating.

### 4.3. Business Impact & ROI
*   **WhatsApp-Attributed Revenue:** Total revenue generated from all sales completed via the platform.
*   **Lead-to-Order Conversion Rate:** The percentage of "Warm" or "Hot" leads that result in a sale.
*   **Resolution Rate (AI vs. Human):** The percentage of support inquiries resolved by the AI without human intervention.
*   **Customer Lifetime Value (LTV):** Estimated total revenue a customer will generate over their lifetime.

## 5. Technical Implementation

### 5.1. Asynchronous Task Processing
*   The analytics process will be implemented as an asynchronous, "fire-and-forget" task.
*   The task will be triggered from within the `ECLAAgent.chat` method in `src/agent/core.py` after the agent has generated its response but before the response is returned to the user.
*   The use of `asyncio.create_task` will ensure that the analytics process does not block the main conversation thread.

### 5.2. Analytics Task Processor
*   A new module will be created at `src/analytics/processor.py`.
*   This module will contain the core logic for the analytics task.
*   It will use a dedicated LLM (`gpt-4.1-nano` via `langchain.chat_models.init_chat_model`) to analyze the conversation history.
*   The LLM will be prompted to return a structured JSON object containing all the key metrics.

### 5.3. Database Integration
*   The analytics data will be stored in the `custom_fields` `JSONB` column of the `contacts` table.
*   A new asynchronous database function, `async_update_contact_analytics`, will be added to `src/multi_tenant_database.py`.
*   This function will perform an "upsert" operation, overwriting the existing analytics data for a contact with the new data. This ensures that there is only one analytics record per contact, which is always up-to-date.

## 6. Success Metrics

*   **Adoption:** Percentage of active users who view the new analytics dashboard.
*   **Performance:** Zero measurable impact on the average agent response time.
*   **User Feedback:** Positive feedback from users on the value and clarity of the new metrics.

## 7. Future Work

*   Develop a dedicated analytics dashboard in the frontend to visualize these metrics.
*   Create an alerting system to notify users of significant events (e.g., a "Hot" lead has been identified).
*   Allow users to customize the analytics and create their own reports.
