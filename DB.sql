drop table if exists paises;
create table paises (
	id_pais int primary key auto_increment,
    pais varchar(50) not null,
    moeda varchar(20) not null,
    cod_moeda varchar(10) not null unique,
    simbolo varchar(5),
    cust_med decimal(10,2),
    imagem varchar(300),
    sigla varchar(2)
);

drop table if exists usuarios;
create table usuarios(
	id_user int primary key auto_increment,
    nome varchar(100),
    username varchar(200) not null unique,
    email varchar(50) not null unique,
    senha varchar(255) not null,
    aceitou_lgpd boolean default 0 not null,
    data_adesao_lgpd date default(current_date()) not null 
);

drop table if exists viagem;
create table viagem(
	id_viagem int primary key auto_increment,
    id_user int not null,
    id_origem int not null,
    id_destino int not null,
    titulo varchar(20),
    data_viagem date,
    data_volta date,
    
    foreign key(id_user) references usuarios(id_user),
    foreign key(id_origem) references paises(id_pais),
    foreign key(id_destino) references paises(id_pais)
);

drop table if exists movimentacoes;
create table movimentacoes(
	id_move int primary key auto_increment,
    id_viagem int not null,
    valor decimal(10,2),
    tipo enum("deposito","retirada"),
    data_move date default(current_date()) not null,
    
    foreign key(id_viagem) references viagem(id_viagem)
);

drop table if exists anotacoes;
create table anotacoes(
	id_nota int primary key auto_increment,
    id_viagem int not null,
    anotacao varchar(300),
    
    foreign key(id_viagem) references viagem(id_viagem)
);

USE viagem_app;

-- 5 países
INSERT INTO paises (pais, moeda, cod_moeda, cust_med, simbolo, imagem, sigla) VALUES
('Brasil','Real','BRL',000.00,'R$',NULL,'br'),
('Japão','Iene','JPY',25000.00,'¥','https://sitecontent.kumon.com.br/site/general/638814864529335322_cultura-japonesa.jpg?width=100','jp'),
('Estados Unidos','Dolar','USD',250.00,'$','https://images.unsplash.com/photo-1485871981521-5b1fd3805eee','us'),
('França','Euro','EUR',180.00,'€','https://images.unsplash.com/photo-1502602898657-3e91760cbb34','fr'),
('Coreia do Sul','Won','KRW',180000.00,'₩','https://omundodiplomatico.com.br/wp-content/uploads/2025/03/seoul-south-korea.webp','kr'),
('Bélgica','Euro','EUR',180.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Brussels-Grand-Place.jpg','be'),
('Bulgária','Euro','EUR',100.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Rila_Monastery.jpg','bg'),
('Croácia','Euro','EUR',130.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Dubrovnik_Croatia.jpg','hr'),
('República Tcheca','Coroa tcheca','CZK',2500.00,'Kč','https://commons.wikimedia.org/wiki/Special:Redirect/file/Charles_Bridge%2C_Prague.jpg','cz'),
('Dinamarca','Coroa dinamarquesa','DKK',1000.00,'kr','https://commons.wikimedia.org/wiki/Special:Redirect/file/Nyhavn_Copenhagen_Photo.jpg','dk'),
('Alemanha','Euro','EUR',130.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Neuschwanstein_Castle%2C_Germany.jpg','de'),
('Estônia','Euro','EUR',120.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Tallinn%2C_Estonia%2C_Wiew_of_Old_Town.jpg','ee'),
('Grécia','Euro','EUR',140.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Santorini%2C_Greece.jpg','gr'),
('Espanha','Euro','EUR',150.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Sagrada_Familia%2C_Barcelona.jpg','es'),
('Itália','Euro','EUR',150.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Colosseum_in_rome.jpg','it'),
('Letônia','Euro','EUR',100.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Riga_Old_Town.jpg','lv'),
('Lituânia','Euro','EUR',100.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Trakai_Castle.jpg','lt'),
('Luxemburgo','Euro','EUR',160.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Luxembourg_City_Landscape_Cityscape_Panorama.jpg','lu'),
('Hungria','Forint','HUF',35000.00,'Ft','https://commons.wikimedia.org/wiki/Special:Redirect/file/Parlamento_de_Budapest_2026.jpg','hu'),
('Malta','Euro','EUR',130.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Comino-Bluelag.jpg','mt'),
('Países Baixos','Euro','EUR',170.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Amsterdam_canals.jpg','nl'),
('Polônia','Zloty','PLN',450.00,'zł','https://commons.wikimedia.org/wiki/Special:Redirect/file/MorskieOko.jpg','pl'),
('Portugal','Euro','EUR',110.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Palacio_Nacional_da_Pena.jpg','pt'),
('Romênia','Leu romeno','RON',100.00,'lei','https://commons.wikimedia.org/wiki/Special:Redirect/file/Bran_Castle_%2827998292264%29.jpg','ro'),
('Eslovênia','Euro','EUR',130.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Lake_bled.jpg','si'),
('Eslováquia','Euro','EUR',110.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Bratislava-Castle.jpg','sk'),
('Finlândia','Euro','EUR',150.00,'€','https://commons.wikimedia.org/wiki/Special:Redirect/file/Helsinki_Cathedral.jpg','fi'),
('Suécia','Coroa sueca','SEK',1000.00,'kr','https://commons.wikimedia.org/wiki/Special:Redirect/file/Stockholm_Gamla_stan.jpg','se'),
('Islândia','Coroa islandesa','ISK',25000.00,'kr','https://commons.wikimedia.org/wiki/Special:Redirect/file/Iceland_Sk%C3%B3gafoss.jpg','is'),
('Noruega','Coroa norueguesa','NOK',1500.00,'kr','https://commons.wikimedia.org/wiki/Special:Redirect/file/Geirangerfjord%2C_Norway.jpg','no'),
('Suíça','Franco suíço','CHF',250.00,'CHF','https://commons.wikimedia.org/wiki/Special:Redirect/file/Matterhorn_Suisse.jpg','ch'),
('Liechtenstein','Franco suíço','CHF',270.00,'CHF','https://commons.wikimedia.org/wiki/Special:Redirect/file/Liechtenstein_Schloss_Vaduz.jpg','li'),
('Reino Unido','Libra esterlina','GBP',180.00,'£','https://commons.wikimedia.org/wiki/Special:Redirect/file/Big_Ben_London_2025.jpg','gb'),
('Nova Zelândia','Dólar neozelandês','NZD',250.00,'NZ$','https://commons.wikimedia.org/wiki/Special:Redirect/file/Milford_Sound%2C_New_Zealand_%28001%29.JPG','nz');
INSERT INTO usuarios (nome, username, email, senha, aceitou_lgpd) VALUES
("Gabriel", "gabriel123", 'gabriel@email.com', '123456', 1);


-- 5 viagens, uma para cada país
INSERT INTO viagem (id_user, id_origem, id_destino, titulo, data_viagem, data_volta) VALUES
(1, 1, 2, 'Viagem Japao', '2026-12-15','2027-01-15'),
(1, 1, 3, 'Viagem EUA', '2027-07-10','2027-07-20'),
(1, 1, 4, 'Viagem Franca', '2027-09-05','2027-09-20'),
(1, 1, 5, 'Viagem Coreia', '2028-03-15', '2028-04-15');


-- 1 movimentação para cada viagem
INSERT INTO movimentacoes (id_viagem, valor, tipo) VALUES
(1, 500.00, 'deposito'),
(1, 1000.00, 'deposito'),
(1, 700.00, 'deposito'),
(2, 200.00, 'deposito'),
(3, 300.00, 'deposito'),
(4, 150.00, 'deposito');


-- 1 anotação para cada viagem
INSERT INTO anotacoes (id_viagem, anotacao) VALUES
(1, 'Ir em um show da ado.'),(1, 'Visitar o Monte Fuji e tirar fotos durante o inverno.'),
(1, 'Conhecer o templo Senso-ji em Asakusa.'),
(1, 'Visitar o cruzamento de Shibuya à noite.'),
(1, 'Conhecer o bairro de Akihabara e suas lojas de tecnologia.'),
(1, 'Experimentar diferentes tipos de ramen em Tokyo.'),
(1, 'Visitar o templo Fushimi Inari em Kyoto.'),
(1, 'Conhecer o bosque de bambu de Arashiyama.'),
(1, 'Fazer um passeio de trem-bala entre Tokyo e Kyoto.'),
(1, 'Visitar o Palácio Imperial de Tokyo.'),
(1, 'Experimentar comidas tradicionais japonesas durante a viagem.'),
(1, 'Fazer um curso de japônes básico.'),
(1, 'Visitar Tokyo, Kyoto e assistir a um show.'),
(2, 'Conhecer Nova York e visitar os principais pontos turisticos.'),
(3, 'Visitar Paris, museus e pontos historicos.');