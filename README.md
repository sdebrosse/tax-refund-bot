# Tax Refund Bot

This tax refund bot demonstrates how Amazon Lex might be used by State and Local government to improve citizen experience. It allows citizens to automatically look up the status of their State tax refund via voice or SMS.

Follow these steps to deploy the demo:
1. Zip up TaxRefund_Export.json. In the Lex console, go to Actions -> Import and select the zip file.
2. Create a Python 2.7 Lambda function with the code in lambda_function.py.
3. Update the Lex bot you deployed in Step #1 to use this Lambda function for validation and fulfillment in the CheckTaxRefundStatus intent. Then Build and Publish the bot.
4. For this Lambda function, create an IAM role with the following managed policies attached:
	* AWSLambdaRole
	* AWSLambdaExecute
	* AmazonDynamoDBReadOnlyAccess

5. Update the Lambda function so it uses the new role created in step 4.
6. Create a DynamoDB table called "taxpayers" with SSN (Number) as the partition key. Refer to taxpayers.csv for sample data.
7. Change line 159 in the Lambda function to the correct region.

You can now test the tax refund bot from within the Lex console. You could integrate the bot with a Connect flow, Facebook or SMS (via Twilio).

Line 135 in the Lambda function has logic to check if the request is from a Lex alias intended to be used with Amazon Connect. If Connect is being used, the Lambda function adds spaces between characters to make the output sound more natural when spoken.
