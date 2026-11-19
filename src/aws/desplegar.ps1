$ErrorActionPreference = "Stop"
$Profile = "cuenta-rues"
$Region = "us-east-2"
$Bucket = "proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026"
$FunctionName = "perfiles-ecommerce"
$ApiName = "perfiles-ecommerce"
$RoleName = "LambdaPerfilesEcommerceRole"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $Here "lambda_modelo"
$Zip = Join-Path $Here "perfiles-ecommerce.zip"
$Key = "modelos/kmeans/lambda/perfiles-ecommerce.zip"

py -3 -c "import zipfile; from pathlib import Path; src=Path(r'$Source'); dest=Path(r'$Zip'); dest.unlink(missing_ok=True); z=zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED)
[ z.write(p, p.relative_to(src).as_posix()) for p in src.rglob('*') if p.is_file() and '__pycache__' not in p.parts ]
z.close(); print('zip', dest.stat().st_size)"
if ($LASTEXITCODE -ne 0) { throw "No se pudo armar el paquete" }

aws s3 cp $Zip "s3://$Bucket/$Key" --profile $Profile --region $Region
if ($LASTEXITCODE -ne 0) { throw "No se pudo subir el paquete a S3" }

$TrustFile = Join-Path $Here "trust-lambda.json"
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
'@ | Set-Content -Path $TrustFile -Encoding ascii
$RoleArn = ""
aws iam get-role --role-name $RoleName --profile $Profile | Out-Null
if ($LASTEXITCODE -eq 0) {
    $RoleArn = aws iam get-role --role-name $RoleName --profile $Profile --query "Role.Arn" --output text
} else {
    aws iam create-role --role-name $RoleName --assume-role-policy-document "file://$($TrustFile -replace '\\','/')" --profile $Profile --description "Ejecuta el API de perfiles de e-commerce" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el rol. Hace falta permiso de IAM en la cuenta SalmiBecerra." }
    aws iam attach-role-policy --role-name $RoleName --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" --profile $Profile | Out-Null
    $RoleArn = aws iam get-role --role-name $RoleName --profile $Profile --query "Role.Arn" --output text
    Start-Sleep -Seconds 12
}

aws lambda get-function --function-name $FunctionName --profile $Profile --region $Region | Out-Null
if ($LASTEXITCODE -eq 0) {
    aws lambda update-function-code --function-name $FunctionName --s3-bucket $Bucket --s3-key $Key --profile $Profile --region $Region | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo actualizar la función" }
} else {
    aws lambda create-function `
        --function-name $FunctionName `
        --runtime python3.12 `
        --handler handler.handler `
        --role $RoleArn `
        --timeout 10 `
        --memory-size 256 `
        --code "S3Bucket=$Bucket,S3Key=$Key" `
        --profile $Profile `
        --region $Region | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear la función" }
}

$ApiId = aws apigatewayv2 get-apis --profile $Profile --region $Region --query "Items[?Name=='$ApiName'].ApiId | [0]" --output text
if (-not $ApiId -or $ApiId -eq "None") {
    $ApiId = aws apigatewayv2 create-api --name $ApiName --protocol-type HTTP --profile $Profile --region $Region --query "ApiId" --output text
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el API" }
    $FunctionArn = aws lambda get-function --function-name $FunctionName --profile $Profile --region $Region --query "Configuration.FunctionArn" --output text
    $IntegrationId = aws apigatewayv2 create-integration --api-id $ApiId --integration-type AWS_PROXY --integration-uri $FunctionArn --payload-format-version "2.0" --profile $Profile --region $Region --query "IntegrationId" --output text
    aws apigatewayv2 create-route --api-id $ApiId --route-key '$default' --target "integrations/$IntegrationId" --profile $Profile --region $Region | Out-Null
    aws apigatewayv2 create-stage --api-id $ApiId --stage-name '$default' --auto-deploy --profile $Profile --region $Region | Out-Null
    $Account = aws sts get-caller-identity --profile $Profile --query "Account" --output text
    aws lambda add-permission --function-name $FunctionName --statement-id apigateway-perfiles --action lambda:InvokeFunction --principal apigateway.amazonaws.com --source-arn "arn:aws:execute-api:${Region}:${Account}:${ApiId}/*" --profile $Profile --region $Region | Out-Null
}

$Url = aws apigatewayv2 get-api --api-id $ApiId --profile $Profile --region $Region --query "ApiEndpoint" --output text
Set-Content -Path (Join-Path $Here "url.txt") -Value $Url -Encoding ascii
Write-Output "SILUETA  $Url/silueta"
Write-Output "SWAGGER  $Url/docs"
Write-Output "CONSULTA $Url/consulta"
