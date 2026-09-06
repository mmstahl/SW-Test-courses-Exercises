write a script to test get_a_room.py   . 

The script works as follows: 

1. randomly picks a check-in and check-out date, between 1 and 30 days. 
2. randomly picks the number of rooms to reserve between 0 and 10 for each room type
3. Run the search for hotels

If the test's result is less than 10, go back to step 1.

4. increase the check out date by 1 day and run the test. 
5. If the result is 0, or checkout date is 30/09/2028, go to step 8. 
6. For the first run of step 4: If the result is the same or below the result of step 3 , continue. From the second run of step 4: If the result is the same or below the result of step 4 , continue. 
7. Otherwise (the result is higher), print the tests of step 3 and the latest test of step 4 and print "Found a bug!!!". Continue to step 8.

8. Following the same format of steps 4 to 7, make the following change to the step 3 test: increment the number of single rooms by 1. Do not change any of the other parameters of test 3. If the result is 0 or the number of requested single room is > 30, stop and continue to step 9. 

9. Do the same as step 8, but for double rooms

10. Do the same as step 9, but for suites

