param()

$ErrorActionPreference = "Stop"

Write-Host "=== Debut de la preparation au deploiement Flask ===" -ForegroundColor Green

try {
    Write-Host "Etape 1/9: Figer les dependances..." -ForegroundColor Yellow
    pip freeze | Out-File -FilePath "requirements.txt" -Encoding UTF8
    Write-Host "OK requirements.txt mis a jour" -ForegroundColor Green

    Write-Host "Etape 2/9: Purger les migrations..." -ForegroundColor Yellow
    if (Test-Path "migrations\versions") {
        Remove-Item "migrations\versions\*" -Force -Recurse
        Write-Host "OK Contenu du dossier migrations/versions/ supprime" -ForegroundColor Green
    } else {
        Write-Host "OK Dossier migrations/versions/ n'existe pas" -ForegroundColor Green
    }

    Write-Host "Etape 3/9: Supprimer la base de donnees de dev..." -ForegroundColor Yellow
    if (Test-Path "data\recruitment-dev.db") {
        Remove-Item "data\recruitment-dev.db" -Force
        Write-Host "OK Base de donnees de developpement supprimee" -ForegroundColor Green
    } else {
        Write-Host "OK Base de donnees de developpement n'existe pas" -ForegroundColor Green
    }

    Write-Host "Etape 4/9: Initialiser les migrations..." -ForegroundColor Yellow
    if (Test-Path "migrations") {
        Remove-Item "migrations" -Force -Recurse
        Write-Host "OK Dossier migrations existant supprime" -ForegroundColor Green
    }
    flask db init
    Write-Host "OK Migrations initialisees" -ForegroundColor Green

    Write-Host "Etape 5/9: Creer la migration..." -ForegroundColor Yellow
    flask db migrate -m "Recreate initial schema from models"
    Write-Host "OK Migration creee" -ForegroundColor Green

    Write-Host "Etape 6/9: Appliquer la migration..." -ForegroundColor Yellow
    flask db upgrade
    Write-Host "OK Migration appliquee" -ForegroundColor Green

    Write-Host "Etape 7/9: Ajouter les fichiers a Git..." -ForegroundColor Yellow
    git add .
    Write-Host "OK Fichiers ajoutes a l'index Git" -ForegroundColor Green

    Write-Host "Etape 8/9: Faire le commit..." -ForegroundColor Yellow
    git commit -m "Ready for production deployment"
    Write-Host "OK Commit cree" -ForegroundColor Green

    Write-Host "Etape 9/9: Pousser sur GitHub..." -ForegroundColor Yellow
    git push origin main
    Write-Host "OK Code pousse sur GitHub" -ForegroundColor Green

    Write-Host "=== Preparation au deploiement terminee avec succes! ===" -ForegroundColor Green
}
catch {
    Write-Host "ERREUR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Le script s'est arrete a cause d'une erreur." -ForegroundColor Red
    exit 1
}

Write-Host "Votre application Flask est maintenant prete pour le deploiement!" -ForegroundColor Cyan
