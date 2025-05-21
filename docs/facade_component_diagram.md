# Facade Component Diagram

## Overview

The following component diagram illustrates the role of the facade within the pytest-analyzer's architecture. It shows how the facade provides backward compatibility with the legacy API while leveraging the new architecture components.

## Component Diagram

```mermaid
graph TD
    %% Client components
    Client[Client Code] --> LegacyService[PytestAnalyzerService]
    Client --> Facade[PytestAnalyzerFacade]
    NewClient[New Client Code] --> DIService[DIPytestAnalyzerService]

    %% Facade pattern components
    subgraph "Backward Compatibility Layer"
        LegacyService --> Facade
    end

    %% New architecture components
    subgraph "New Architecture"
        Facade --> StateMachine[AnalyzerStateMachine]
        DIService --> StateMachine

        %% DI Container
        DIContainer[DI Container] --- Facade
        DIContainer --- DIService
        DIContainer --> ExtractorImpl[Extractor Implementations]
        DIContainer --> AnalyzerImpl[Analyzer Implementations]
        DIContainer --> SuggesterImpl[Suggester Implementations]
        DIContainer --> ApplierImpl[Applier Implementations]
        DIContainer --> LLMService[LLM Service]

        %% State Machine
        StateMachine --> Extraction[Extraction State]
        StateMachine --> Analysis[Analysis State]
        StateMachine --> Suggestion[Suggestion State]
        StateMachine --> Application[Application State]

        %% Protocol implementations
        Extraction --> Extractor[Extractor Protocol]
        Analysis --> Analyzer[Analyzer Protocol]
        Suggestion --> Suggester[Suggester Protocol]
        Application --> Applier[Applier Protocol]

        %% Protocol concrete implementations
        Extractor --> ExtractorImpl
        Analyzer --> AnalyzerImpl
        Suggester --> SuggesterImpl
        Applier --> ApplierImpl
    end

    %% Styling
    classDef client fill:#f9f,stroke:#333,stroke-width:2px;
    classDef facade fill:#bbf,stroke:#333,stroke-width:2px;
    classDef component fill:#dfd,stroke:#333,stroke-width:1px;
    classDef protocol fill:#ffc,stroke:#333,stroke-width:1px;
    classDef state fill:#eff,stroke:#333,stroke-width:1px;

    class Client,NewClient client;
    class LegacyService,Facade,DIService facade;
    class DIContainer,StateMachine component;
    class Extractor,Analyzer,Suggester,Applier protocol;
    class Extraction,Analysis,Suggestion,Application state;
```

## Key Components

### Client Layer
- **Client Code**: Existing code using the legacy API
- **New Client Code**: New code using the DI-based API
- **PytestAnalyzerService**: Legacy class name that inherits from the facade
- **PytestAnalyzerFacade**: Facade implementation that provides backward compatibility
- **DIPytestAnalyzerService**: New service that directly uses the DI container

### Architecture Layer
- **DI Container**: Manages dependencies and component instantiation
- **AnalyzerStateMachine**: Coordinates the analysis workflow

### Protocol Layer
- **Extractor Protocol**: Interface for extracting test failures
- **Analyzer Protocol**: Interface for analyzing failures
- **Suggester Protocol**: Interface for suggesting fixes
- **Applier Protocol**: Interface for applying fixes

### Implementation Layer
- **Extractor Implementations**: Concrete extractor classes
- **Analyzer Implementations**: Concrete analyzer classes
- **Suggester Implementations**: Concrete suggester classes
- **Applier Implementations**: Concrete applier classes
- **LLM Service**: Language model service for AI-based suggestions

## Flow of Control

1. Client code interacts with either the legacy service, facade, or DI-based service
2. The facade delegates to the state machine
3. The state machine coordinates the workflow through various states
4. Each state interacts with the appropriate protocol
5. Protocols are implemented by concrete implementations
6. The DI container manages the instantiation and configuration of all components

This architecture provides a clean migration path from the legacy API to the new architecture while maintaining backward compatibility.
