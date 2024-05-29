# Load environment variables from config.env
source ./../.env

# Python script command
python_command="python3 order_raft.py"

# Loop through each port
for i in 3 2 1; do
    # Get port and host from environment variables
    port_var="ORDER_PORT_$i"
    host_var="ORDER_HOST_$i"
    unique_id_var="ORDER_ID_$i"

    port="${!port_var}"
    host="${!host_var}"
    unique_id="${!unique_id_var}"
    
    # Construct command with port and host
    command="$python_command --port $port --host $host --unique_id $unique_id"

    # Run Python script on the specified port
    $command &
    echo "Python script started on Port $port and Host $host initialised with Order ID $unique_id"
done

# Wait for all background processes to finish
wait