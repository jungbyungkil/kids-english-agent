param location string = resourceGroup().location
param namePrefix string

// Core resources
resource openai 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: '${namePrefix}-aoai'
  location: location
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: '${namePrefix}-aoai'
    publicNetworkAccess: 'Enabled'
  }
}

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: '${namePrefix}-search'
  location: location
  sku: { name: 'basic' }
  properties: {
    networkRuleSet: { ipRules: [] }
    publicNetworkAccess: 'enabled'
    hostingMode: 'default'
  }
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: '${namePrefix}-cosmos'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        failoverPriority: 0
        isZoneRedundant: false
        locationName: location
      }
    ]
    capabilities: [ { name: 'EnableMongo' } ]
    publicNetworkAccess: 'Enabled'
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: toLower('${namePrefix}stg')
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${namePrefix}-plan'
  location: location
  sku: { name: 'Y1', tier: 'Dynamic' } // Consumption
}

resource funcapp 'Microsoft.Web/sites@2023-12-01' = {
  name: '${namePrefix}-func'
  location: location
  kind: 'functionapp'
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      appSettings: [
        { name: 'AzureWebJobsStorage', value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};EndpointSuffix=core.windows.net' },
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' },
        { name: 'AZURE_OPENAI_ENDPOINT', value: 'https://${openai.name}.openai.azure.com' },
        { name: 'AZURE_SEARCH_ENDPOINT', value: 'https://${search.name}.search.windows.net' }
      ]
    }
    httpsOnly: true
  }
  identity: { type: 'SystemAssigned' }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-appi'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}

output aoaiEndpoint string = 'https://${openai.name}.openai.azure.com'
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output functionAppName string = funcapp.name

