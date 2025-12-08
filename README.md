Hướng dẫn cách Demo
1. Chạy trên máy ảo
    - Mở 3 máy ảo (host), mỗi cái một IP riêng, 1 cái chạy start_backend.py, 1 cái chạy start_sampleapp.py, 1 cái chạy start_proxy.py, để xem cú pháp chạy thế nào thì ghi lệnh: python3 (tên file) -h, ví dụ: 
    
    python3 start_sampleapp.py -h

    - Truy cập web thông qua IP của server chạy proxy.py, ví dụ như máy chạy proxy có IP 192.168.1.1 thì sẽ truy cập thông qua http://192.168.1.1:8080
    - Phải đăng kí tài khoản trước thì mới chạy được bước sau
    - Chạy local engine để khởi động peer, ví dụ đã đăng kí tài khoản với username = NgoChung, password = 3changlinhngulam trên web rồi, bật thêm 1 máy host nữa để chạy local engine, nếu muốn xem cú pháp chạy thì ghi lệnh tương tự như mấy file trên, còn đây là 1 câu lệnh chạy để ví dụ:

    python3 start_peer.py --server-ip 192.168.1.10 --server-port 9201 --username NgoChung --password 3changlinhngulam --web-port 5001

    --server-ip: là ip của máy host đang chạy engine này, nghĩa là đây là ip để peer hoặc proxy liên lạc tới engine này
    --server-port: port để giao tiếp với các peer khác
    --web-port: port để proxy liên lạc tới engine này

    - Khi nó hiện Registered - Online thì là thành công, peer đã online và giờ có thể đăng nhập trên web để coi các peer đang hoạt động và bắt đầu connect để chat

    - Lên web mà nó vẫn là để local engine: OFFLINE thì phải coi lại từ cái bước chạy peer vì peer chưa online thì chưa thể chat được

    - Để test thì dùng thêm 1 host nữa để chạy cho 1 user nữa, nhưng mà không biết nếu để 2 terminal để chạy local engine cho 2 user trên cùng 1 máy ảo thì có được không (cái này chưa test)