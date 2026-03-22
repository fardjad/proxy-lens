using System.Net.Http.Headers;
using System.Text.Json;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var appName = GetRequiredEnvironmentVariable("APP_NAME");
var downstreamUrl = Environment.GetEnvironmentVariable("DOWNSTREAM_URL");
var downstreamName = Environment.GetEnvironmentVariable("DOWNSTREAM_NAME");

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHttpClient("downstream", client =>
{
    client.DefaultRequestHeaders.Accept.Add(
        new MediaTypeWithQualityHeaderValue("application/json"));
    client.Timeout = TimeSpan.FromSeconds(10);
});

builder.Services
    .AddOpenTelemetry()
    .ConfigureResource(resource => resource.AddService(appName))
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation());

var app = builder.Build();

app.MapGet("/", async (HttpContext context, IHttpClientFactory httpClientFactory) =>
{
    if (string.IsNullOrWhiteSpace(downstreamUrl))
    {
        return Results.Json(new
        {
            service = appName,
            message = $"hello from {appName}",
        });
    }

    try
    {
        var client = httpClientFactory.CreateClient("downstream");
        using var response = await client.GetAsync(downstreamUrl, context.RequestAborted);
        response.EnsureSuccessStatusCode();

        var downstream = await response.Content.ReadFromJsonAsync<JsonElement>(
            cancellationToken: context.RequestAborted);

        return Results.Json(new
        {
            service = appName,
            message = $"{appName} called {downstreamName}",
            downstream,
        });
    }
    catch (Exception exception)
    {
        return Results.Json(new
        {
            service = appName,
            error = $"downstream request failed: {exception.Message}",
        }, statusCode: StatusCodes.Status502BadGateway);
    }
});

await app.RunAsync();

return;

static string GetRequiredEnvironmentVariable(string name) =>
    Environment.GetEnvironmentVariable(name)
    ?? throw new InvalidOperationException($"{name} is required");
