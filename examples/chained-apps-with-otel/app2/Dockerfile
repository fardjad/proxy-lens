FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build

WORKDIR /src

COPY app2.csproj /src/app2.csproj
RUN dotnet restore /src/app2.csproj

COPY Program.cs /src/Program.cs
RUN dotnet publish /src/app2.csproj -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:10.0

WORKDIR /app

ENV ASPNETCORE_HTTP_PORTS=

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/publish /app
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

EXPOSE 9443

ENTRYPOINT ["/app/entrypoint.sh"]
