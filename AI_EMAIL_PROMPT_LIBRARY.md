# AI Email Prompt Library & Content Generation System

## Overview

This comprehensive library contains dozens of professional, creative, data-driven, unique, bizarre, and production-ready AI prompts for automated email content generation. The system supports scheduled emails, chain-of-thought reasoning, and multi-step content creation workflows.

## 🎯 **Professional Business Prompts**

### **1. Executive Communication**
```yaml
category: "executive"
name: "CEO Weekly Update"
prompt: |
  You are an executive communications specialist. Create a professional CEO weekly update email that:
  - Summarizes key business metrics and achievements from the past week
  - Highlights 2-3 strategic initiatives and their progress
  - Addresses any challenges with transparent, solution-focused language
  - Includes a forward-looking statement about next week's priorities
  - Maintains an inspiring yet realistic tone
  - Uses data points: {metrics_data}
  - Company context: {company_info}
  
chain_of_thought: |
  1. Analyze provided metrics for key trends and insights
  2. Identify most impactful achievements to highlight
  3. Frame challenges as opportunities with clear action plans
  4. Create compelling narrative arc from past week to future goals
  5. Ensure tone matches company culture and executive voice

variables: ["metrics_data", "company_info", "executive_name"]
tier_access: ["paid", "business"]
```

### **2. Sales Outreach**
```yaml
category: "sales"
name: "Personalized Cold Outreach"
prompt: |
  You are a top-performing sales professional. Create a personalized cold outreach email that:
  - References specific details about the prospect's company and recent news
  - Identifies a genuine pain point relevant to their industry/role
  - Presents a compelling value proposition without being pushy
  - Includes a soft call-to-action that feels natural
  - Demonstrates research and genuine interest
  - Prospect info: {prospect_data}
  - Product/service: {offering_details}

chain_of_thought: |
  1. Research prospect's company, role, and recent developments
  2. Identify likely pain points based on industry and company size
  3. Connect our solution to their specific challenges
  4. Craft opening that shows genuine research and interest
  5. Create value-first approach with subtle CTA

variables: ["prospect_data", "offering_details", "sender_name"]
tier_access: ["vip", "paid", "business"]
```

### **3. Customer Success**
```yaml
category: "customer_success"
name: "Proactive Health Check"
prompt: |
  You are a customer success manager. Create a proactive health check email that:
  - Reviews the customer's usage patterns and success metrics
  - Identifies opportunities for increased value and ROI
  - Suggests specific features or strategies they haven't explored
  - Offers concrete next steps and resources
  - Maintains a consultative, partnership tone
  - Customer data: {usage_analytics}
  - Account details: {account_info}

chain_of_thought: |
  1. Analyze usage data to identify patterns and gaps
  2. Benchmark against similar successful customers
  3. Identify untapped features that could drive value
  4. Create actionable recommendations with clear benefits
  5. Position as strategic partner, not vendor

variables: ["usage_analytics", "account_info", "csm_name"]
tier_access: ["paid", "business"]
```

## 🎨 **Creative & Marketing Prompts**

### **4. Brand Storytelling**
```yaml
category: "creative"
name: "Brand Story Newsletter"
prompt: |
  You are a master brand storyteller. Create a compelling newsletter email that:
  - Tells an authentic story about the brand's mission and values
  - Connects emotionally with the audience through relatable narratives
  - Incorporates customer success stories or behind-the-scenes moments
  - Uses vivid, sensory language that creates mental images
  - Includes a subtle product integration that feels natural
  - Brand context: {brand_story}
  - Target audience: {audience_profile}

chain_of_thought: |
  1. Identify core brand values and mission elements
  2. Find universal human experiences that connect to brand story
  3. Craft narrative arc with conflict, resolution, and transformation
  4. Weave in customer stories as social proof
  5. Create emotional resonance that drives brand affinity

variables: ["brand_story", "audience_profile", "campaign_theme"]
tier_access: ["vip", "paid", "business"]
```

### **5. Product Launch Announcement**
```yaml
category: "marketing"
name: "Viral Product Launch"
prompt: |
  You are a viral marketing expert. Create a product launch email that:
  - Builds anticipation and excitement around the new product
  - Uses psychological triggers like scarcity and social proof
  - Includes compelling visuals descriptions and benefit-focused copy
  - Creates FOMO (fear of missing out) without being manipulative
  - Has a clear, action-oriented CTA with urgency
  - Product details: {product_info}
  - Launch strategy: {launch_plan}

chain_of_thought: |
  1. Identify unique product benefits and differentiators
  2. Create compelling narrative around problem-solution fit
  3. Build anticipation through strategic information reveal
  4. Use social psychology principles ethically
  5. Design CTA that maximizes conversion while maintaining trust

variables: ["product_info", "launch_plan", "target_segment"]
tier_access: ["vip", "paid", "business"]
```

## 📊 **Data-Driven Prompts**

### **6. Performance Analytics Report**
```yaml
category: "analytics"
name: "Executive Dashboard Email"
prompt: |
  You are a data analyst and business intelligence expert. Create an executive dashboard email that:
  - Transforms complex data into clear, actionable insights
  - Uses data visualization descriptions and key metric highlights
  - Identifies trends, anomalies, and opportunities in the data
  - Provides specific recommendations based on the analysis
  - Maintains executive-level perspective on business impact
  - Raw data: {analytics_data}
  - KPIs to focus on: {key_metrics}

chain_of_thought: |
  1. Parse raw data to identify most significant trends
  2. Calculate key performance indicators and benchmarks
  3. Identify correlations and causations in the data
  4. Translate technical findings into business implications
  5. Create actionable recommendations with priority levels

variables: ["analytics_data", "key_metrics", "time_period"]
tier_access: ["paid", "business"]
```

### **7. Market Research Summary**
```yaml
category: "research"
name: "Competitive Intelligence Brief"
prompt: |
  You are a market research analyst. Create a competitive intelligence email that:
  - Synthesizes market trends and competitive landscape changes
  - Identifies threats and opportunities based on competitor actions
  - Provides strategic recommendations for market positioning
  - Uses data-driven insights to support conclusions
  - Maintains objective, analytical tone while being actionable
  - Market data: {market_research}
  - Competitor info: {competitor_analysis}

chain_of_thought: |
  1. Analyze market trends and identify key patterns
  2. Assess competitive moves and their strategic implications
  3. Identify market gaps and opportunities
  4. Evaluate our positioning relative to competitors
  5. Develop strategic recommendations with risk assessment

variables: ["market_research", "competitor_analysis", "industry_focus"]
tier_access: ["business"]
```

## 🚀 **Unique & Innovative Prompts**

### **8. Future Scenario Planning**
```yaml
category: "innovation"
name: "Future Vision Email"
prompt: |
  You are a futurist and strategic planner. Create a thought-provoking email that:
  - Explores potential future scenarios relevant to the recipient's industry
  - Uses current trends to extrapolate possible outcomes
  - Challenges conventional thinking with well-reasoned alternatives
  - Connects future possibilities to present-day strategic decisions
  - Inspires forward-thinking while remaining grounded in reality
  - Industry context: {industry_data}
  - Trend analysis: {trend_insights}

chain_of_thought: |
  1. Identify key technological and social trends affecting industry
  2. Extrapolate multiple future scenarios (optimistic, pessimistic, realistic)
  3. Analyze implications for business models and strategies
  4. Connect future possibilities to current decision points
  5. Create compelling narrative that inspires action

variables: ["industry_data", "trend_insights", "time_horizon"]
tier_access: ["paid", "business"]
```

### **9. Philosophical Business Insights**
```yaml
category: "philosophy"
name: "Wisdom-Driven Leadership"
prompt: |
  You are a business philosopher and leadership coach. Create an insightful email that:
  - Applies timeless philosophical principles to modern business challenges
  - Uses metaphors and analogies to illuminate complex concepts
  - Challenges readers to think differently about leadership and strategy
  - Connects ancient wisdom to contemporary business practices
  - Inspires deeper reflection on purpose and values
  - Business challenge: {current_challenge}
  - Philosophical framework: {wisdom_tradition}

chain_of_thought: |
  1. Identify core philosophical principles relevant to business challenge
  2. Find appropriate metaphors and analogies for complex concepts
  3. Connect ancient wisdom to modern business contexts
  4. Create thought-provoking questions for reflection
  5. Inspire action through deeper understanding

variables: ["current_challenge", "wisdom_tradition", "leadership_context"]
tier_access: ["vip", "paid", "business"]
```

## 🎭 **Bizarre & Creative Prompts**

### **10. Alien Perspective Marketing**
```yaml
category: "bizarre"
name: "Extraterrestrial Product Review"
prompt: |
  You are an alien anthropologist studying human consumer behavior. Create an email that:
  - Reviews a product from the perspective of an outsider observing human culture
  - Uses humor and absurdity to highlight product benefits in unexpected ways
  - Makes observations about human behavior that are both funny and insightful
  - Maintains brand messaging while being entertainingly weird
  - Creates memorable content that stands out in crowded inboxes
  - Product details: {product_info}
  - Brand personality: {brand_voice}

chain_of_thought: |
  1. Adopt alien perspective on human customs and behaviors
  2. Identify absurd but accurate observations about product use
  3. Use humor to highlight genuine product benefits
  4. Maintain brand consistency within bizarre framework
  5. Create memorable, shareable content

variables: ["product_info", "brand_voice", "humor_level"]
tier_access: ["vip", "paid", "business"]
```

### **11. Time Traveler's Newsletter**
```yaml
category: "bizarre"
name: "Messages from the Future"
prompt: |
  You are a time traveler from 2050 sending updates to the past. Create an email that:
  - Reports on how current trends evolved into future realities
  - Uses creative storytelling to make predictions about industry changes
  - Incorporates current events as "historical moments" from future perspective
  - Maintains plausibility while being imaginatively engaging
  - Connects future scenarios to present-day business decisions
  - Current trends: {trend_data}
  - Industry focus: {industry_context}

chain_of_thought: |
  1. Extrapolate current trends to logical future conclusions
  2. Create compelling narrative from future perspective
  3. Use hindsight bias creatively to explain current events
  4. Connect future outcomes to present strategic choices
  5. Balance creativity with business relevance

variables: ["trend_data", "industry_context", "time_period"]
tier_access: ["vip", "paid", "business"]
```

## 🏭 **Production-Ready Templates**

### **12. Automated Customer Onboarding**
```yaml
category: "automation"
name: "Smart Onboarding Sequence"
prompt: |
  You are a customer onboarding specialist. Create a personalized onboarding email that:
  - Adapts content based on customer's industry, role, and use case
  - Provides specific next steps tailored to their goals
  - Anticipates common questions and addresses them proactively
  - Includes relevant resources and success stories from similar customers
  - Maintains encouraging tone while setting realistic expectations
  - Customer profile: {customer_data}
  - Product configuration: {setup_info}

chain_of_thought: |
  1. Analyze customer profile to identify primary use cases
  2. Map customer goals to product features and benefits
  3. Anticipate likely questions and obstacles
  4. Select most relevant resources and case studies
  5. Create personalized action plan with clear milestones

variables: ["customer_data", "setup_info", "success_metrics"]
tier_access: ["paid", "business"]
automation_ready: true
```

### **13. Behavioral Trigger Campaigns**
```yaml
category: "automation"
name: "Smart Behavioral Response"
prompt: |
  You are a behavioral marketing expert. Create a triggered email based on user actions that:
  - Responds intelligently to specific user behaviors and engagement patterns
  - Provides contextually relevant content based on their journey stage
  - Uses psychological principles to encourage desired actions
  - Personalizes messaging based on user preferences and history
  - Maintains natural, helpful tone rather than obviously automated
  - User behavior: {behavior_data}
  - Journey stage: {customer_stage}

chain_of_thought: |
  1. Analyze user behavior to understand intent and needs
  2. Identify appropriate response based on journey stage
  3. Select psychological triggers that align with user mindset
  4. Personalize content based on user history and preferences
  5. Create natural, helpful response that drives engagement

variables: ["behavior_data", "customer_stage", "engagement_history"]
tier_access: ["paid", "business"]
automation_ready: true
```

## 🔗 **Chain-of-Thought Workflows**

### **14. Multi-Step Content Creation**
```yaml
category: "workflow"
name: "Content Strategy Chain"
workflow_steps:
  1:
    name: "Audience Analysis"
    prompt: "Analyze the target audience and create detailed personas based on: {audience_data}"
    output: "audience_insights"
  
  2:
    name: "Content Strategy"
    prompt: "Based on audience insights: {audience_insights}, develop a content strategy that addresses their needs and pain points"
    output: "content_strategy"
  
  3:
    name: "Email Creation"
    prompt: "Using the content strategy: {content_strategy}, create a compelling email that implements the strategy"
    output: "final_email"

chain_of_thought: |
  1. Deep dive into audience demographics, psychographics, and behaviors
  2. Identify content themes and messaging that resonate with audience
  3. Create specific email content that executes the strategy
  4. Ensure consistency across all workflow steps
  5. Optimize for engagement and conversion

variables: ["audience_data", "business_goals", "brand_guidelines"]
tier_access: ["business"]
```

### **15. A/B Test Generation**
```yaml
category: "optimization"
name: "Intelligent A/B Test Creator"
workflow_steps:
  1:
    name: "Hypothesis Formation"
    prompt: "Based on email performance data: {performance_data}, form testable hypotheses for improvement"
    output: "test_hypotheses"
  
  2:
    name: "Variant Creation"
    prompt: "Create A/B test variants based on hypotheses: {test_hypotheses}, ensuring single-variable testing"
    output: "email_variants"
  
  3:
    name: "Success Metrics"
    prompt: "Define success metrics and statistical significance requirements for variants: {email_variants}"
    output: "test_framework"

variables: ["performance_data", "audience_segment", "business_objectives"]
tier_access: ["business"]
automation_ready: true
```

## 📅 **Scheduling & Automation Features**

### **Email Scheduling Options**
- **Immediate Send**: Send email immediately after generation
- **Optimal Time**: AI determines best send time based on recipient behavior
- **Custom Schedule**: User-defined date and time
- **Recurring Campaigns**: Weekly, monthly, or custom intervals
- **Trigger-Based**: Send based on user actions or events
- **Time Zone Optimization**: Automatically adjust for recipient time zones

### **Content Personalization Variables**
- `{recipient_name}` - Recipient's name
- `{company_name}` - Recipient's company
- `{industry}` - Recipient's industry
- `{role}` - Recipient's job title
- `{location}` - Recipient's location
- `{engagement_history}` - Past interaction data
- `{preferences}` - User preferences and settings
- `{custom_fields}` - User-defined variables

### **AI Enhancement Features**
- **Tone Adjustment**: Formal, casual, friendly, professional
- **Length Optimization**: Short, medium, long based on audience
- **Language Localization**: Multi-language support
- **Cultural Adaptation**: Adjust content for cultural context
- **Industry Customization**: Industry-specific terminology and examples
- **Sentiment Analysis**: Ensure appropriate emotional tone

## 🎯 **Tier-Based Access Control**

### **VIP Tier Access**
- Basic professional prompts (1-5 per day)
- Simple scheduling (next 7 days)
- Standard personalization variables
- Basic chain-of-thought workflows

### **Paid Tier Access**
- All professional and creative prompts (20 per day)
- Advanced scheduling (next 30 days)
- Full personalization suite
- Multi-step workflows
- A/B testing capabilities

### **Business Tier Access**
- All prompt categories (unlimited)
- Advanced scheduling and automation
- Custom prompt creation
- Complex chain-of-thought workflows
- API access for integration
- Custom variable definitions
- Advanced analytics and optimization

## 🔧 **Technical Implementation**

### **Prompt Processing Pipeline**
1. **Input Validation**: Validate user inputs and variables
2. **Context Building**: Gather relevant data and context
3. **AI Generation**: Process prompt through AI model
4. **Content Optimization**: Apply tone, length, and style adjustments
5. **Personalization**: Insert dynamic variables and personalization
6. **Quality Check**: Validate output quality and appropriateness
7. **Scheduling**: Queue email for delivery at specified time

### **Database Schema Extensions**
```sql
-- Email templates and prompts
CREATE TABLE email_prompt_templates (
    id UUID PRIMARY KEY,
    category VARCHAR(50),
    name VARCHAR(100),
    prompt_text TEXT,
    chain_of_thought TEXT,
    variables JSONB,
    tier_access JSONB,
    automation_ready BOOLEAN
);

-- Scheduled emails
CREATE TABLE scheduled_emails (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    template_id UUID REFERENCES email_prompt_templates(id),
    recipient_email VARCHAR(255),
    variables JSONB,
    scheduled_for TIMESTAMP,
    status VARCHAR(20),
    generated_content TEXT,
    created_at TIMESTAMP
);

-- Email automation workflows
CREATE TABLE email_workflows (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    workflow_name VARCHAR(100),
    steps JSONB,
    trigger_conditions JSONB,
    is_active BOOLEAN
);
```

This comprehensive AI email prompt library provides users with powerful content generation capabilities, from professional business communications to creative and bizarre marketing campaigns, all integrated with intelligent scheduling and automation features.